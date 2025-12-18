"""
Fun-ASR All-in-One Docker Service
FastAPI + WebSocket + Gradio UI
"""
import os
import io
import time
import json
import asyncio
import tempfile
import logging
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

import torch
import torchaudio
import numpy as np
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global model instances
model = None
vad_model = None
model_path = None

# Audio longer than this (seconds) will use VAD segmentation
VAD_THRESHOLD_SECONDS = 30

def get_model():
    """Get or load the ASR model (singleton, always in GPU memory)"""
    global model, model_path
    if model is None:
        from funasr import AutoModel
        model_dir = os.environ.get("MODEL_DIR", "FunAudioLLM/Fun-ASR-Nano-2512")
        device = "cuda:0"
        logger.info(f"Loading model {model_dir} on {device}...")
        start = time.time()
        model = AutoModel(
            model=model_dir,
            trust_remote_code=True,
            remote_code="./model.py",
            device=device,
            disable_update=True,
        )
        model_path = model.model_path
        logger.info(f"Model loaded in {time.time()-start:.2f}s")
    return model

def get_vad_model():
    """Get or load VAD model for long audio segmentation"""
    global vad_model
    if vad_model is None:
        from funasr import AutoModel
        logger.info("Loading VAD model...")
        start = time.time()
        vad_model = AutoModel(model="fsmn-vad", model_revision="v2.0.4", device="cuda:0", disable_update=True)
        logger.info(f"VAD model loaded in {time.time()-start:.2f}s")
    return vad_model

def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds"""
    try:
        info = torchaudio.info(audio_path)
        return info.num_frames / info.sample_rate
    except:
        return 0

def transcribe(audio_path: str, language: str = "auto", hotwords: List[str] = None, itn: bool = True) -> dict:
    """Core transcription function with VAD for long audio"""
    m = get_model()
    start = time.time()
    
    duration = get_audio_duration(audio_path)
    
    # For long audio, use VAD segmentation to avoid hallucination
    if duration > VAD_THRESHOLD_SECONDS:
        logger.info(f"Long audio ({duration:.1f}s), using VAD segmentation...")
        vad = get_vad_model()
        # Get VAD segments: [[start_ms, end_ms], ...]
        vad_res = vad.generate(input=audio_path)
        segments = vad_res[0]["value"] if vad_res and "value" in vad_res[0] else []
        
        if not segments:
            logger.warning("VAD returned no segments, falling back to direct recognition")
            res = m.generate(input=[audio_path], cache={}, batch_size=1, hotwords=hotwords or [], language=language, itn=itn)
            text = res[0]["text"] if res else ""
        else:
            # Load audio and process each segment
            waveform, sr = torchaudio.load(audio_path)
            if sr != 16000:
                waveform = torchaudio.functional.resample(waveform, sr, 16000)
                sr = 16000
            waveform = waveform.mean(dim=0, keepdim=True) if waveform.shape[0] > 1 else waveform
            
            texts = []
            for i, seg in enumerate(segments):
                start_sample = int(seg[0] * sr / 1000)
                end_sample = int(seg[1] * sr / 1000)
                chunk = waveform[:, start_sample:end_sample]
                
                # Save chunk to temp file
                chunk_path = f"/tmp/chunk_{i}.wav"
                torchaudio.save(chunk_path, chunk, sr)
                
                res = m.generate(input=[chunk_path], cache={}, batch_size=1, hotwords=hotwords or [], language=language, itn=itn)
                if res and res[0]["text"]:
                    texts.append(res[0]["text"])
                
                os.remove(chunk_path)
            
            text = "".join(texts)
            logger.info(f"Processed {len(segments)} VAD segments")
    else:
        res = m.generate(input=[audio_path], cache={}, batch_size=1, hotwords=hotwords or [], language=language, itn=itn)
        text = res[0]["text"] if res else ""
    
    elapsed = time.time() - start
    return {"text": text, "time": round(elapsed, 3)}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload model on startup"""
    get_model()
    logger.info("Model preloaded and ready")
    yield

app = FastAPI(
    title="Fun-ASR API",
    description="Speech Recognition API based on Fun-ASR-Nano",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== REST API ====================

@app.get("/health")
async def health():
    """Health check endpoint"""
    gpu_id = os.environ.get('NVIDIA_VISIBLE_DEVICES', '0').split(',')[0]
    gpu_info = {}
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits', f'--id={gpu_id}'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            used, total = result.stdout.strip().split(', ')
            gpu_info = {"memory_used_mb": int(used), "memory_total_mb": int(total), "gpu_id": gpu_id}
    except:
        pass
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "gpu": gpu_info
    }

@app.post("/v1/audio/transcriptions")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    hotwords: str = Form(""),
    itn: bool = Form(True),
):
    """
    Transcribe audio file (OpenAI Whisper compatible endpoint)
    
    - **file**: Audio file (wav, mp3, etc.)
    - **language**: Language code (auto, zh, en, ja)
    - **hotwords**: Comma-separated hotwords for better recognition
    - **itn**: Inverse text normalization (convert numbers to digits, etc.)
    """
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename).suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        hw_list = [w.strip() for w in hotwords.split(",") if w.strip()] if hotwords else []
        result = transcribe(tmp_path, language, hw_list, itn)
        return {"text": result["text"], "duration": result["time"]}
    finally:
        os.unlink(tmp_path)

@app.post("/api/transcribe")
async def api_transcribe(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    hotwords: str = Form(""),
    itn: bool = Form(True),
):
    """Alternative transcription endpoint"""
    return await transcribe_audio(file, language, hotwords, itn)

# ==================== WebSocket Streaming ====================

@app.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    """
    WebSocket endpoint for streaming audio transcription.
    
    Protocol:
    1. Client sends JSON config: {"language": "auto", "hotwords": [], "itn": true}
    2. Client sends audio chunks (binary)
    3. Client sends JSON: {"action": "end"} to finish
    4. Server responds with transcription result
    
    For real-time partial results, audio is accumulated and transcribed periodically.
    """
    await websocket.accept()
    audio_buffer = io.BytesIO()
    config = {"language": "auto", "hotwords": [], "itn": True}
    sample_rate = 16000
    last_transcribe_time = 0
    partial_interval = 2.0  # Send partial results every 2 seconds
    
    try:
        while True:
            data = await websocket.receive()
            
            if "text" in data:
                msg = json.loads(data["text"])
                if msg.get("action") == "end":
                    # Final transcription
                    if audio_buffer.tell() > 0:
                        audio_buffer.seek(0)
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                            tmp.write(audio_buffer.read())
                            tmp_path = tmp.name
                        try:
                            result = transcribe(tmp_path, config["language"], config["hotwords"], config["itn"])
                            await websocket.send_json({"type": "final", "text": result["text"], "time": result["time"]})
                        finally:
                            os.unlink(tmp_path)
                    break
                elif msg.get("action") == "config":
                    config.update({k: v for k, v in msg.items() if k in ("language", "hotwords", "itn", "sample_rate")})
                    sample_rate = msg.get("sample_rate", 16000)
                    await websocket.send_json({"type": "config_ack", "config": config})
                    
            elif "bytes" in data:
                audio_buffer.write(data["bytes"])
                
                # Send partial results periodically
                current_time = time.time()
                if current_time - last_transcribe_time > partial_interval and audio_buffer.tell() > sample_rate * 2:  # At least 1 second of audio
                    last_transcribe_time = current_time
                    audio_buffer.seek(0)
                    audio_data = audio_buffer.read()
                    audio_buffer.seek(0, 2)  # Back to end
                    
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        tmp.write(audio_data)
                        tmp_path = tmp.name
                    try:
                        result = transcribe(tmp_path, config["language"], config["hotwords"], config["itn"])
                        await websocket.send_json({"type": "partial", "text": result["text"]})
                    except Exception as e:
                        logger.warning(f"Partial transcription failed: {e}")
                    finally:
                        os.unlink(tmp_path)
                        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})

# ==================== Gradio UI ====================

LANGUAGES = {
    "自动检测 / Auto": "auto",
    "中文 / Chinese": "zh", 
    "English": "en",
    "日本語 / Japanese": "ja",
}

def gradio_transcribe(audio, language, hotwords, itn):
    """Gradio interface function"""
    if audio is None:
        return "请上传或录制音频 / Please upload or record audio", ""
    
    hw_list = [w.strip() for w in hotwords.split(",") if w.strip()] if hotwords else []
    lang_code = LANGUAGES.get(language, "auto")
    
    result = transcribe(audio, lang_code, hw_list, itn)
    
    # Get audio duration
    try:
        info = torchaudio.info(audio)
        audio_duration = info.num_frames / info.sample_rate
    except:
        audio_duration = 0
    
    timer_text = f"⏱️ 识别耗时: {result['time']:.2f}s | 音频时长: {audio_duration:.2f}s | RTF: {result['time']/audio_duration:.2f}x" if audio_duration > 0 else f"⏱️ 识别耗时: {result['time']:.2f}s"
    
    return result["text"], timer_text

with gr.Blocks(title="Fun-ASR 语音识别") as demo:
    gr.Markdown("""
    <div style="text-align: center; margin-bottom: 1rem;">
    <h1>🎙️ Fun-ASR 语音识别</h1>
    <p>基于 Fun-ASR-Nano-2512 的端到端语音识别服务</p>
    </div>
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            audio_input = gr.Audio(
                label="🎤 上传或录制音频",
                type="filepath",
                sources=["upload", "microphone"],
            )
            
            with gr.Accordion("⚙️ 参数设置", open=True):
                language = gr.Dropdown(
                    choices=list(LANGUAGES.keys()),
                    value="自动检测 / Auto",
                    label="语言 / Language",
                )
                hotwords = gr.Textbox(
                    label="热词 / Hotwords",
                    placeholder="用逗号分隔，如：人工智能,机器学习",
                    info="提高特定词汇的识别准确率",
                )
                itn = gr.Checkbox(
                    value=True,
                    label="文本规整 (ITN)",
                    info="将数字、日期等转换为标准格式",
                )
            
            submit_btn = gr.Button("🚀 开始识别", variant="primary", size="lg")
        
        with gr.Column(scale=1):
            result_text = gr.Textbox(
                label="📝 识别结果",
                lines=8,
            )
            timer_display = gr.Markdown()
    
    submit_btn.click(
        fn=gradio_transcribe,
        inputs=[audio_input, language, hotwords, itn],
        outputs=[result_text, timer_display],
    )
    
    gr.Markdown("""
    ---
    ### 📡 API 使用
    
    **REST API:**
    ```bash
    curl -X POST http://localhost:8189/v1/audio/transcriptions \\
      -F "file=@audio.wav" \\
      -F "language=auto"
    ```
    
    **WebSocket:** `ws://localhost:8189/ws/transcribe`
    
    📖 [API 文档](/docs) | [Swagger UI](/docs)
    """)

# Mount Gradio app
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8189))
    uvicorn.run(app, host="0.0.0.0", port=port)
