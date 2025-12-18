# Fun-ASR MCP Guide

Model Context Protocol (MCP) interface for Fun-ASR speech recognition.

## Configuration

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "fun-asr": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/path/to/Fun-ASR",
      "env": {
        "MODEL_DIR": "FunAudioLLM/Fun-ASR-Nano-2512",
        "NVIDIA_VISIBLE_DEVICES": "0"
      }
    }
  }
}
```

## Available Tools

### transcribe

Transcribe audio file to text.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| audio_path | string | ✅ | - | Path to audio file (wav, mp3, etc.) |
| language | string | ❌ | "auto" | Language: "auto", "zh", "en", "ja" |
| hotwords | list[str] | ❌ | [] | Hotwords for better recognition |
| itn | bool | ❌ | true | Inverse text normalization |

**Example:**
```python
result = await mcp.call_tool("transcribe", {
    "audio_path": "/path/to/audio.wav",
    "language": "zh",
    "hotwords": ["人工智能", "机器学习"],
    "itn": True
})
# Returns: {"text": "识别结果", "time": 0.45}
```

### transcribe_base64

Transcribe base64-encoded audio.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| audio_base64 | string | ✅ | - | Base64-encoded audio data |
| audio_format | string | ❌ | "wav" | Audio format (wav, mp3, etc.) |
| language | string | ❌ | "auto" | Language code |
| hotwords | list[str] | ❌ | [] | Hotwords |
| itn | bool | ❌ | true | ITN |

### get_gpu_status

Get GPU memory and utilization status.

**Returns:**
```json
{
  "gpu_id": "0",
  "name": "NVIDIA L40S",
  "memory_used_mb": 8500,
  "memory_total_mb": 46068,
  "utilization_percent": 15,
  "model_loaded": true
}
```

### get_model_info

Get information about the loaded model.

**Returns:**
```json
{
  "model_loaded": true,
  "model_dir": "FunAudioLLM/Fun-ASR-Nano-2512",
  "supported_languages": ["auto", "zh", "en", "ja"],
  "features": ["Chinese (7 dialects, 26 regional accents)", ...]
}
```

### preload_model

Preload model into GPU memory.

**Returns:**
```json
{
  "status": "success",
  "message": "Model loaded and ready",
  "load_time": 12.5
}
```

## MCP vs REST API

| Feature | MCP | REST API |
|---------|-----|----------|
| Use case | Programmatic access | HTTP clients |
| Protocol | stdio/SSE | HTTP/WebSocket |
| File input | Local path | Upload |
| Streaming | ❌ | ✅ (WebSocket) |
| Best for | AI agents, automation | Web apps, curl |

## Language Codes

| Code | Language | Notes |
|------|----------|-------|
| auto | Auto-detect | Recommended for mixed content |
| zh | Chinese | Includes 7 dialects, 26 accents |
| en | English | Multiple accents |
| ja | Japanese | - |
