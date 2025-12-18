"""
Fun-ASR All-in-One Docker Service
FastAPI + WebSocket + Gradio UI with Progress
"""
import os
import io
import time
import json
import asyncio
import tempfile
import logging
import uuid
import threading
from pathlib import Path
from typing import Optional, List, Callable, Generator
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

import torch
import torchaudio
import numpy as np
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect, HTTPException, Form, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global model instances
model = None
vad_model = None
model_path = None

# Task storage for async API
tasks = {}
executor = ThreadPoolExecutor(max_workers=2)

# Audio longer than this (seconds) will use VAD segmentation
VAD_THRESHOLD_SECONDS = 30

def get_model():
    """Get or load the ASR model (singleton, always in GPU memory)"""
    global model, model_path
    if model is None:
        from funasr import AutoModel
        # Use local cached path for offline operation
        model_id = os.environ.get("MODEL_DIR", "FunAudioLLM/Fun-ASR-Nano-2512")
        local_model_path = f"/root/.cache/modelscope/hub/models/{model_id}"
        
        # Check if local model exists, otherwise use model_id (will download)
        if os.path.exists(local_model_path):
            model_dir = local_model_path
            logger.info(f"Using local model: {model_dir}")
        else:
            model_dir = model_id
            logger.info(f"Model not cached, will download: {model_dir}")
        
        device = "cuda:0"
        logger.info(f"Loading model on {device}...")
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
        # Use local cached path for offline operation
        local_vad_path = "/root/.cache/modelscope/hub/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
        
        if os.path.exists(local_vad_path):
            model_dir = local_vad_path
            logger.info(f"Using local VAD model: {model_dir}")
        else:
            model_dir = "fsmn-vad"
            logger.info("VAD model not cached, will download")
        
        logger.info("Loading VAD model...")
        start = time.time()
        vad_model = AutoModel(model=model_dir, device="cuda:0", disable_update=True)
        logger.info(f"VAD model loaded in {time.time()-start:.2f}s")
    return vad_model

def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds"""
    try:
        info = torchaudio.info(audio_path)
        return info.num_frames / info.sample_rate
    except:
        return 0

def transcribe_with_progress(
    audio_path: str, 
    language: str = "auto", 
    hotwords: List[str] = None, 
    itn: bool = True,
    progress_callback: Callable[[int, int, str], None] = None
) -> dict:
    """
    Core transcription function with VAD for long audio and progress callback.
    
    Args:
        progress_callback: Function(current, total, partial_text) called during processing
    """
    m = get_model()
    start = time.time()
    
    duration = get_audio_duration(audio_path)
    
    # For long audio, use VAD segmentation to avoid hallucination
    if duration > VAD_THRESHOLD_SECONDS:
        logger.info(f"Long audio ({duration:.1f}s), using VAD segmentation...")
        vad = get_vad_model()
        vad_res = vad.generate(input=audio_path)
        segments = vad_res[0]["value"] if vad_res and "value" in vad_res[0] else []
        
        if not segments:
            logger.warning("VAD returned no segments, falling back to direct recognition")
            if progress_callback:
                progress_callback(0, 1, "")
            res = m.generate(input=[audio_path], cache={}, batch_size=1, hotwords=hotwords or [], language=language, itn=itn)
            text = res[0]["text"] if res else ""
            if progress_callback:
                progress_callback(1, 1, text)
        else:
            # Load audio and process each segment
            waveform, sr = torchaudio.load(audio_path)
            if sr != 16000:
                waveform = torchaudio.functional.resample(waveform, sr, 16000)
                sr = 16000
            waveform = waveform.mean(dim=0, keepdim=True) if waveform.shape[0] > 1 else waveform
            
            texts = []
            total = len(segments)
            for i, seg in enumerate(segments):
                start_sample = int(seg[0] * sr / 1000)
                end_sample = int(seg[1] * sr / 1000)
                chunk = waveform[:, start_sample:end_sample]
                
                chunk_path = f"/tmp/chunk_{uuid.uuid4().hex[:8]}.wav"
                torchaudio.save(chunk_path, chunk, sr)
                
                try:
                    res = m.generate(input=[chunk_path], cache={}, batch_size=1, hotwords=hotwords or [], language=language, itn=itn)
                    if res and res[0]["text"]:
                        texts.append(res[0]["text"])
                finally:
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
                
                if progress_callback:
                    progress_callback(i + 1, total, "".join(texts))
            
            text = "".join(texts)
            logger.info(f"Processed {len(segments)} VAD segments")
    else:
        if progress_callback:
            progress_callback(0, 1, "")
        res = m.generate(input=[audio_path], cache={}, batch_size=1, hotwords=hotwords or [], language=language, itn=itn)
        text = res[0]["text"] if res else ""
        if progress_callback:
            progress_callback(1, 1, text)
    
    elapsed = time.time() - start
    return {"text": text, "time": round(elapsed, 3), "duration": round(duration, 2)}

def transcribe(audio_path: str, language: str = "auto", hotwords: List[str] = None, itn: bool = True) -> dict:
    """Simple transcription without progress callback"""
    return transcribe_with_progress(audio_path, language, hotwords, itn, None)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload model on startup"""
    get_model()
    logger.info("Model preloaded and ready")
    yield

app = FastAPI(
    title="Fun-ASR API",
    description="Speech Recognition API based on Fun-ASR-Nano with VAD segmentation",
    version="1.2.0",
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
    gpu_info = {}
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            used, total = result.stdout.strip().split(', ')
            gpu_info = {"memory_used_mb": int(used), "memory_total_mb": int(total)}
    except:
        pass
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "vad_loaded": vad_model is not None,
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
    Supports long audio with automatic VAD segmentation.
    """
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename).suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        hw_list = [w.strip() for w in hotwords.split(",") if w.strip()] if hotwords else []
        # Run in thread pool to not block event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, transcribe, tmp_path, language, hw_list, itn)
        return {"text": result["text"], "duration": result["time"], "audio_duration": result.get("duration", 0)}
    finally:
        os.unlink(tmp_path)

@app.post("/v1/audio/transcriptions/stream")
async def transcribe_audio_stream(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    hotwords: str = Form(""),
    itn: bool = Form(True),
):
    """
    Transcribe audio with Server-Sent Events for progress updates.
    Returns streaming response with progress and final result.
    """
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename).suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    hw_list = [w.strip() for w in hotwords.split(",") if w.strip()] if hotwords else []
    
    def generate():
        progress_data = {"current": 0, "total": 0, "text": ""}
        
        def progress_cb(current, total, text):
            progress_data["current"] = current
            progress_data["total"] = total
            progress_data["text"] = text
        
        # Start transcription in background
        result_holder = [None]
        def run_transcribe():
            result_holder[0] = transcribe_with_progress(tmp_path, language, hw_list, itn, progress_cb)
        
        thread = threading.Thread(target=run_transcribe)
        thread.start()
        
        last_current = -1
        while thread.is_alive():
            if progress_data["current"] != last_current and progress_data["total"] > 0:
                last_current = progress_data["current"]
                yield f"data: {json.dumps({'type': 'progress', 'current': progress_data['current'], 'total': progress_data['total'], 'text': progress_data['text']})}\n\n"
            time.sleep(0.1)
        
        thread.join()
        os.unlink(tmp_path)
        
        if result_holder[0]:
            yield f"data: {json.dumps({'type': 'complete', 'text': result_holder[0]['text'], 'duration': result_holder[0]['time']})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

# ==================== WebSocket Streaming ====================

@app.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    """WebSocket endpoint for streaming audio transcription with progress."""
    await websocket.accept()
    audio_buffer = io.BytesIO()
    config = {"language": "auto", "hotwords": [], "itn": True}
    
    try:
        while True:
            data = await websocket.receive()
            
            if "text" in data:
                msg = json.loads(data["text"])
                if msg.get("action") == "end":
                    if audio_buffer.tell() > 0:
                        audio_buffer.seek(0)
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                            tmp.write(audio_buffer.read())
                            tmp_path = tmp.name
                        
                        try:
                            async def send_progress(current, total, text):
                                await websocket.send_json({
                                    "type": "progress", 
                                    "current": current, 
                                    "total": total,
                                    "text": text[:200] + "..." if len(text) > 200 else text
                                })
                            
                            # Run with progress in thread
                            loop = asyncio.get_event_loop()
                            result = await loop.run_in_executor(
                                executor, 
                                transcribe, 
                                tmp_path, 
                                config["language"], 
                                config["hotwords"], 
                                config["itn"]
                            )
                            await websocket.send_json({"type": "final", "text": result["text"], "time": result["time"]})
                        finally:
                            os.unlink(tmp_path)
                    break
                elif msg.get("action") == "config":
                    config.update({k: v for k, v in msg.items() if k in ("language", "hotwords", "itn")})
                    await websocket.send_json({"type": "config_ack", "config": config})
                    
            elif "bytes" in data:
                audio_buffer.write(data["bytes"])
                        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass

# ==================== Gradio UI with Progress ====================

LANGUAGES = {
    "自动检测 / Auto": "auto",
    "中文 / Chinese": "zh", 
    "English": "en",
    "日本語 / Japanese": "ja",
}

def gradio_transcribe(audio, language, hotwords, itn, progress=gr.Progress()):
    """Gradio interface function with progress bar"""
    if audio is None:
        return "请上传或录制音频 / Please upload or record audio", ""
    
    hw_list = [w.strip() for w in hotwords.split(",") if w.strip()] if hotwords else []
    lang_code = LANGUAGES.get(language, "auto")
    
    # Get audio duration first
    try:
        info = torchaudio.info(audio)
        audio_duration = info.num_frames / info.sample_rate
    except:
        audio_duration = 0
    
    # Progress tracking
    progress_state = {"current": 0, "total": 1, "text": ""}
    
    def progress_callback(current, total, text):
        progress_state["current"] = current
        progress_state["total"] = total
        progress_state["text"] = text
        if total > 0:
            progress(current / total, desc=f"处理中 {current}/{total} 段...")
    
    progress(0, desc="开始识别...")
    result = transcribe_with_progress(audio, lang_code, hw_list, itn, progress_callback)
    progress(1, desc="完成!")
    
    # Format timer
    rtf = result['time'] / audio_duration if audio_duration > 0 else 0
    if progress_state["total"] > 1:
        timer_text = f"⏱️ 识别耗时: {result['time']:.2f}s | 音频时长: {audio_duration:.2f}s | RTF: {rtf:.2f}x | VAD分段: {progress_state['total']}段"
    else:
        timer_text = f"⏱️ 识别耗时: {result['time']:.2f}s | 音频时长: {audio_duration:.2f}s | RTF: {rtf:.2f}x"
    
    return result["text"], timer_text

with gr.Blocks(title="Fun-ASR 语音识别") as demo:
    gr.Markdown("""
    <div style="text-align: center; margin-bottom: 1rem;">
    <h1>🎙️ Fun-ASR 语音识别</h1>
    <p>基于 Fun-ASR-Nano-2512 的端到端语音识别服务 | 支持超长音频自动分段</p>
    </div>
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            audio_input = gr.Audio(
                label="🎤 上传或录制音频 (支持任意时长)",
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
                lines=12,
                max_lines=20,
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
    
    **REST API (同步):**
    ```bash
    curl -X POST http://localhost:8189/v1/audio/transcriptions \\
      -F "file=@audio.wav" -F "language=auto"
    ```
    
    **REST API (流式进度):**
    ```bash
    curl -X POST http://localhost:8189/v1/audio/transcriptions/stream \\
      -F "file=@long_audio.mp3" -F "language=zh"
    ```
    
    **WebSocket:** `ws://localhost:8189/ws/transcribe`
    
    📖 [API 文档](/docs) | 💡 超过30秒的音频自动使用VAD分段处理
    """)

# Mount Gradio app
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8189))
    uvicorn.run(app, host="0.0.0.0", port=port)
