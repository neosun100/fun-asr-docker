# 🎙️ Fun-ASR All-in-One Docker

[![Docker Pulls](https://img.shields.io/docker/pulls/neosun/fun-asr?style=flat-square&logo=docker)](https://hub.docker.com/r/neosun/fun-asr)
[![Docker Image Version](https://img.shields.io/docker/v/neosun/fun-asr?style=flat-square&logo=docker&sort=semver)](https://hub.docker.com/r/neosun/fun-asr)

**基于 Fun-ASR-Nano-2512 的端到端语音识别服务，支持超长音频自动分段处理**

一条 Docker 命令即可获得 Web UI + REST API + WebSocket + 流式进度

---

## ✨ 特性

| 特性 | 说明 |
|------|------|
| 🎯 **Fun-ASR-Nano-2512** | 阿里通义实验室最新 800M 参数端到端 ASR 模型 |
| 🔊 **VAD 自动分段** | 超过 30 秒的音频自动使用 FSMN-VAD 分段，避免幻觉 |
| 📊 **实时进度** | UI 进度条 + SSE 流式 API，实时显示处理进度 |
| 🔌 **OpenAI 兼容** | `/v1/audio/transcriptions` 兼容 Whisper API |
| 🌍 **多语言** | 支持 31 种语言、7 种中文方言、26 种地方口音 |
| ⚡ **高性能** | RTF < 0.1，6 分钟音频约 40 秒处理完成 |

---

## 🚀 快速开始

```bash
docker run -d \
  --name fun-asr \
  --gpus '"device=0"' \
  -p 8189:8189 \
  -v fun-asr-models:/root/.cache \
  neosun/fun-asr:latest
```

首次启动需下载模型（约 1.8GB），之后从缓存加载（约 30 秒）。

打开 http://localhost:8189 即可使用 🎉

---

## 📦 部署方式

### Docker Run

```bash
docker run -d \
  --name fun-asr \
  --gpus '"device=0"' \
  -p 8189:8189 \
  -v fun-asr-models:/root/.cache \
  --restart unless-stopped \
  neosun/fun-asr:v1.2.0
```

### Docker Compose

```yaml
# docker-compose.yml
services:
  fun-asr:
    image: neosun/fun-asr:v1.2.0
    container_name: fun-asr
    restart: unless-stopped
    ports:
      - "8189:8189"
    volumes:
      - fun-asr-models:/root/.cache
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["0"]
              capabilities: [gpu]

volumes:
  fun-asr-models:
```

```bash
docker compose up -d
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | `8189` | 服务端口 |
| `MODEL_DIR` | `FunAudioLLM/Fun-ASR-Nano-2512` | 模型路径 |

---

## 🖥️ Web UI

访问 http://localhost:8189 使用 Web 界面：

### 功能
- 📤 上传音频文件（支持 wav, mp3, m4a, flac 等）
- 🎤 实时录音识别
- 📊 **进度条显示**（长音频分段处理时实时更新）
- ⚙️ 参数设置：语言、热词、ITN

### 界面说明
- **语言选择**：自动检测 / 中文 / English / 日本語
- **热词**：用逗号分隔，提高特定词汇识别率
- **文本规整 (ITN)**：将数字、日期转换为标准格式

### 输出信息
```
⏱️ 识别耗时: 39.19s | 音频时长: 367.96s | RTF: 0.11x | VAD分段: 33段
```

---

## 📡 REST API

### 端点列表

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/v1/audio/transcriptions` | POST | 同步转录（OpenAI 兼容） |
| `/v1/audio/transcriptions/stream` | POST | 流式转录（SSE 进度） |
| `/ws/transcribe` | WebSocket | 实时流式转录 |
| `/docs` | GET | Swagger API 文档 |

---

### 1. 健康检查

```bash
curl http://localhost:8189/health
```

响应：
```json
{
  "status": "healthy",
  "model_loaded": true,
  "vad_loaded": true,
  "gpu": {
    "memory_used_mb": 4065,
    "memory_total_mb": 46068
  }
}
```

---

### 2. 同步转录 API

**适用场景**：短音频（< 5 分钟）或不需要进度显示

```bash
curl -X POST http://localhost:8189/v1/audio/transcriptions \
  -F "file=@audio.wav" \
  -F "language=auto" \
  -F "hotwords=人工智能,机器学习" \
  -F "itn=true"
```

**参数说明**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `file` | File | 必填 | 音频文件 |
| `language` | string | `auto` | 语言代码：auto, zh, en, ja |
| `hotwords` | string | `""` | 热词，逗号分隔 |
| `itn` | bool | `true` | 是否启用文本规整 |

**响应**：
```json
{
  "text": "开放时间早上九点至下午五点。",
  "duration": 0.771,
  "audio_duration": 5.62
}
```

---

### 3. 流式转录 API（推荐用于长音频）

**适用场景**：长音频，需要实时进度反馈

```bash
curl -X POST http://localhost:8189/v1/audio/transcriptions/stream \
  -F "file=@long_audio.mp3" \
  -F "language=zh" \
  --no-buffer
```

**响应格式**：Server-Sent Events (SSE)

```
data: {"type": "progress", "current": 1, "total": 33, "text": "哎呀，真是有趣的设计呢..."}

data: {"type": "progress", "current": 2, "total": 33, "text": "哎呀，真是有趣的设计呢。偶尔尝试下..."}

... (更多进度更新)

data: {"type": "complete", "text": "完整识别结果...", "duration": 39.191}
```

**事件类型**：

| type | 说明 | 字段 |
|------|------|------|
| `progress` | 处理进度 | `current`, `total`, `text`（部分结果） |
| `complete` | 处理完成 | `text`（完整结果）, `duration` |

---

### 4. Python 客户端示例

#### 同步调用

```python
import requests

def transcribe(audio_path, language="auto"):
    with open(audio_path, "rb") as f:
        response = requests.post(
            "http://localhost:8189/v1/audio/transcriptions",
            files={"file": f},
            data={"language": language}
        )
    return response.json()

result = transcribe("audio.wav", "zh")
print(result["text"])
```

#### 流式调用（带进度）

```python
import requests
import json

def transcribe_with_progress(audio_path, language="auto"):
    with open(audio_path, "rb") as f:
        response = requests.post(
            "http://localhost:8189/v1/audio/transcriptions/stream",
            files={"file": f},
            data={"language": language},
            stream=True
        )
    
    for line in response.iter_lines():
        if line:
            line = line.decode("utf-8")
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data["type"] == "progress":
                    print(f"进度: {data['current']}/{data['total']}")
                elif data["type"] == "complete":
                    return data["text"]
    return None

text = transcribe_with_progress("long_audio.mp3", "zh")
print(text)
```

#### JavaScript/Node.js 示例

```javascript
// 同步调用
async function transcribe(audioPath) {
  const formData = new FormData();
  formData.append('file', fs.createReadStream(audioPath));
  formData.append('language', 'auto');
  
  const response = await fetch('http://localhost:8189/v1/audio/transcriptions', {
    method: 'POST',
    body: formData
  });
  return response.json();
}

// 流式调用
async function transcribeWithProgress(audioPath, onProgress) {
  const formData = new FormData();
  formData.append('file', fs.createReadStream(audioPath));
  
  const response = await fetch('http://localhost:8189/v1/audio/transcriptions/stream', {
    method: 'POST',
    body: formData
  });
  
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const lines = decoder.decode(value).split('\n');
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        if (data.type === 'progress') {
          onProgress(data.current, data.total, data.text);
        } else if (data.type === 'complete') {
          return data.text;
        }
      }
    }
  }
}
```

---

### 5. WebSocket API

**适用场景**：实时录音流式识别

**连接**：`ws://localhost:8189/ws/transcribe`

**协议流程**：

```
1. 客户端连接 WebSocket
2. 客户端发送配置: {"action": "config", "language": "zh", "hotwords": [], "itn": true}
3. 服务端确认: {"type": "config_ack", "config": {...}}
4. 客户端发送音频数据 (binary)
5. 客户端发送结束信号: {"action": "end"}
6. 服务端返回结果: {"type": "final", "text": "...", "time": 1.23}
```

**Python WebSocket 示例**：

```python
import asyncio
import websockets
import json

async def realtime_transcribe(audio_path):
    async with websockets.connect("ws://localhost:8189/ws/transcribe") as ws:
        # 发送配置
        await ws.send(json.dumps({
            "action": "config",
            "language": "zh",
            "hotwords": [],
            "itn": True
        }))
        config_ack = await ws.recv()
        print("Config:", config_ack)
        
        # 发送音频数据
        with open(audio_path, "rb") as f:
            while chunk := f.read(4096):
                await ws.send(chunk)
        
        # 发送结束信号
        await ws.send(json.dumps({"action": "end"}))
        
        # 接收结果
        result = await ws.recv()
        return json.loads(result)

result = asyncio.run(realtime_transcribe("audio.wav"))
print(result["text"])
```

---

## 📊 性能基准

**测试环境**：NVIDIA L40S GPU

### 处理速度

| 音频时长 | VAD 分段 | 处理时间 | RTF |
|----------|----------|----------|-----|
| 3 秒 | 1 段 | 0.44s | 0.15x |
| 5 秒 | 1 段 | 0.77s | 0.15x |
| 6 分钟 | 33 段 | 39s | 0.11x |
| 2 小时 | ~660 段 | ~13 分钟 | ~0.11x |

> RTF (Real-Time Factor) < 1.0 表示处理速度快于实时播放

### VAD 分段机制

- 音频 ≤ 30 秒：直接识别
- 音频 > 30 秒：自动使用 FSMN-VAD 分段后逐段识别
- 避免长音频产生幻觉（重复输出）

---

## 🗣️ 支持的语言

### 主要语言
- 中文、英语、日语、韩语
- 德语、西班牙语、法语、意大利语、俄语

### 中文方言
- 粤语、四川话、东北话、上海话、闽南语等 18 种方言

### 特殊能力
- 高噪声环境识别
- 歌词识别
- 热词增强
- ITN 文本规整

---

## 🔧 高级配置

### Nginx 反向代理

```nginx
server {
    listen 80;
    server_name asr.example.com;

    location / {
        proxy_pass http://127.0.0.1:8189;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 1800s;  # 30 分钟超时，支持超长音频
    }
}
```

### GPU 选择

```bash
# 使用 GPU 0
docker run --gpus '"device=0"' ...

# 使用 GPU 2
docker run --gpus '"device=2"' ...

# 使用多个 GPU（模型只用一个，但可以运行多个容器）
docker run --gpus '"device=0"' -p 8189:8189 --name fun-asr-0 ...
docker run --gpus '"device=1"' -p 8190:8189 --name fun-asr-1 ...
```

---

## 📋 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v1.2.0 | 2024-12-18 | 异步 API + UI 进度条 + SSE 流式端点 |
| v1.1.0 | 2024-12-18 | VAD 分段支持长音频（修复幻觉问题） |
| v1.0.0 | 2024-12-18 | 初始版本：FastAPI + Gradio + WebSocket |

---

## 🛠️ 技术栈

- **ASR 模型**：[Fun-ASR-Nano-2512](https://huggingface.co/FunAudioLLM/Fun-ASR-Nano-2512)
- **VAD 模型**：[FSMN-VAD](https://modelscope.cn/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch)
- **框架**：FastAPI + Gradio
- **运行时**：PyTorch + CUDA 12.1
- **容器**：Docker + NVIDIA Container Toolkit

---

## 🙏 致谢

- [FunAudioLLM/Fun-ASR](https://github.com/FunAudioLLM/Fun-ASR) - Fun-ASR-Nano 模型
- [Alibaba DAMO Academy](https://github.com/alibaba-damo-academy/FunASR) - FunASR 框架

---

## 📄 许可证

Apache License 2.0
