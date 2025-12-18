"""
Fun-ASR MCP Server
Model Context Protocol interface for speech recognition
"""
import os
import sys
import tempfile
import base64
from typing import Optional, List

# Add current directory to path for model.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fun-asr")

# Global model instance (persistent in memory)
_model = None
_model_path = None

def get_model():
    """Get or load the ASR model (singleton, always in GPU memory)"""
    global _model, _model_path
    if _model is None:
        from funasr import AutoModel
        model_dir = os.environ.get("MODEL_DIR", "FunAudioLLM/Fun-ASR-Nano-2512")
        device = f"cuda:{os.environ.get('NVIDIA_VISIBLE_DEVICES', '0').split(',')[0]}"
        print(f"[MCP] Loading model {model_dir} on {device}...", file=sys.stderr)
        _model = AutoModel(
            model=model_dir,
            trust_remote_code=True,
            remote_code="./model.py",
            device=device,
        )
        _model_path = _model.model_path
        print(f"[MCP] Model loaded successfully", file=sys.stderr)
    return _model

@mcp.tool()
def transcribe(
    audio_path: str,
    language: str = "auto",
    hotwords: Optional[List[str]] = None,
    itn: bool = True,
) -> dict:
    """
    Transcribe audio file to text.
    
    Args:
        audio_path: Path to the audio file (wav, mp3, etc.)
        language: Language code - "auto" (detect), "zh" (Chinese), "en" (English), "ja" (Japanese)
        hotwords: List of hotwords to improve recognition accuracy
        itn: Inverse text normalization (convert numbers to digits, etc.)
    
    Returns:
        Dictionary with "text" (transcription) and "time" (processing time in seconds)
    """
    import time
    
    if not os.path.exists(audio_path):
        return {"error": f"File not found: {audio_path}"}
    
    model = get_model()
    start = time.time()
    
    try:
        res = model.generate(
            input=[audio_path],
            cache={},
            batch_size=1,
            hotwords=hotwords or [],
            language=language,
            itn=itn,
        )
        elapsed = time.time() - start
        text = res[0]["text"] if res else ""
        return {"text": text, "time": round(elapsed, 3)}
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def transcribe_base64(
    audio_base64: str,
    audio_format: str = "wav",
    language: str = "auto",
    hotwords: Optional[List[str]] = None,
    itn: bool = True,
) -> dict:
    """
    Transcribe base64-encoded audio to text.
    
    Args:
        audio_base64: Base64-encoded audio data
        audio_format: Audio format extension (wav, mp3, etc.)
        language: Language code - "auto", "zh", "en", "ja"
        hotwords: List of hotwords to improve recognition accuracy
        itn: Inverse text normalization
    
    Returns:
        Dictionary with "text" (transcription) and "time" (processing time)
    """
    try:
        audio_data = base64.b64decode(audio_base64)
    except Exception as e:
        return {"error": f"Invalid base64 data: {e}"}
    
    with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name
    
    try:
        return transcribe(tmp_path, language, hotwords, itn)
    finally:
        os.unlink(tmp_path)

@mcp.tool()
def get_gpu_status() -> dict:
    """
    Get current GPU memory status.
    
    Returns:
        Dictionary with GPU memory information
    """
    gpu_id = os.environ.get('NVIDIA_VISIBLE_DEVICES', '0').split(',')[0]
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.used,memory.total,utilization.gpu', 
             '--format=csv,noheader,nounits', f'--id={gpu_id}'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(',')]
            return {
                "gpu_id": gpu_id,
                "name": parts[0],
                "memory_used_mb": int(parts[1]),
                "memory_total_mb": int(parts[2]),
                "utilization_percent": int(parts[3]),
                "model_loaded": _model is not None,
            }
    except Exception as e:
        return {"error": str(e)}
    return {"error": "Failed to get GPU status"}

@mcp.tool()
def get_model_info() -> dict:
    """
    Get information about the loaded ASR model.
    
    Returns:
        Dictionary with model information
    """
    return {
        "model_loaded": _model is not None,
        "model_dir": os.environ.get("MODEL_DIR", "FunAudioLLM/Fun-ASR-Nano-2512"),
        "model_path": _model_path,
        "supported_languages": ["auto", "zh", "en", "ja"],
        "features": [
            "Chinese (7 dialects, 26 regional accents)",
            "English (multiple accents)",
            "Japanese",
            "High-noise recognition",
            "Lyric recognition",
            "Hotword boosting",
            "Inverse text normalization (ITN)",
        ],
    }

@mcp.tool()
def preload_model() -> dict:
    """
    Preload the ASR model into GPU memory.
    Call this to ensure the model is ready before transcription.
    
    Returns:
        Dictionary with status and model info
    """
    import time
    start = time.time()
    model = get_model()
    elapsed = time.time() - start
    return {
        "status": "success",
        "message": "Model loaded and ready",
        "load_time": round(elapsed, 2),
        "model_path": _model_path,
    }

if __name__ == "__main__":
    # Preload model on startup
    get_model()
    mcp.run()
