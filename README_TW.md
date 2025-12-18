[English](README.md) | [简体中文](README_CN.md) | [繁體中文](README_TW.md) | [日本語](README_JP.md)

<div align="center">

# 🎙️ Fun-ASR All-in-One Docker

[![Docker Pulls](https://img.shields.io/docker/pulls/neosun/fun-asr?style=flat-square&logo=docker)](https://hub.docker.com/r/neosun/fun-asr)
[![Docker Image Version](https://img.shields.io/docker/v/neosun/fun-asr?style=flat-square&logo=docker&sort=semver)](https://hub.docker.com/r/neosun/fun-asr)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=flat-square)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/neosun100/fun-asr-docker?style=flat-square&logo=github)](https://github.com/neosun100/fun-asr-docker)

**基於 Fun-ASR-Nano-2512 的生產級語音識別服務**

🎁 **All-in-One 映像**：模型已預下載，執行時無需網路！

一條 Docker 命令即可獲得 Web UI + REST API + WebSocket + 即時進度

[快速開始](#-快速開始) • [功能特性](#-功能特性) • [API 文檔](#-api-參考) • [效能測試](#-效能基準)

</div>

---

## 📸 介面截圖

![Web UI](images/ui-screenshot.png)

---

## ✨ 功能特性

| 特性 | 說明 |
|------|------|
| 🎯 **Fun-ASR-Nano-2512** | 阿里通義實驗室最新 800M 參數端到端 ASR 模型 |
| 🔊 **VAD 自動分段** | 超過 30 秒的音訊自動分段，避免幻覺問題 |
| 📊 **即時進度顯示** | UI 進度條 + SSE 串流 API |
| 🔌 **OpenAI 相容** | `/v1/audio/transcriptions` 相容 Whisper API |
| 🌍 **多語言支援** | 31 種語言、7 種中文方言、26 種地方口音 |
| ⚡ **高效能** | RTF < 0.1，6 分鐘音訊約 40 秒處理完成 |

---

## 🚀 快速開始

```bash
docker run -d \
  --name fun-asr \
  --gpus '"device=0"' \
  -p 8189:8189 \
   \
  neosun/fun-asr:latest
```

**All-in-One**：模型已預下載到映像中，服務約 30 秒啟動完成！

開啟 http://localhost:8189 即可使用 🎉

---

## 📦 安裝部署

### 前置條件

- Docker 20.10+
- NVIDIA GPU（顯存 4GB+）
- NVIDIA Container Toolkit

### Docker Run

```bash
docker run -d \
  --name fun-asr \
  --gpus '"device=0"' \
  -p 8189:8189 \
   \
  --restart unless-stopped \
  neosun/fun-asr:v1.3.1
```

### Docker Compose

```yaml
# docker-compose.yml
services:
  fun-asr:
    image: neosun/fun-asr:v1.3.1
    container_name: fun-asr
    restart: unless-stopped
    ports:
      - "8189:8189"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["0"]
              capabilities: [gpu]

```

```bash
docker compose up -d
```

### 健康檢查

```bash
curl http://localhost:8189/health
# {"status":"healthy","model_loaded":true,"vad_loaded":true,"gpu":{...}}
```

---

## ⚙️ 配置說明

### 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `PORT` | `8189` | 服務埠號 |
| `MODEL_DIR` | `FunAudioLLM/Fun-ASR-Nano-2512` | 模型路徑 |

### 資料卷

| 路徑 | 說明 |
|------|------|
| `/root/.cache` | 模型快取（持久化） |

---

## 🖥️ Web UI 使用

存取 http://localhost:8189 使用 Web 介面：

### 功能
- 📤 上傳音訊檔案（支援 wav, mp3, m4a, flac 等）
- 🎤 即時錄音識別
- 📊 **進度條顯示**（長音訊分段處理時即時更新）
- ⚙️ 參數設定：語言、熱詞、ITN

### 輸出資訊
```
⏱️ 識別耗時: 39.19s | 音訊時長: 367.96s | RTF: 0.11x | VAD分段: 33段
```

---

## 📡 API 參考

### 端點列表

| 端點 | 方法 | 說明 |
|------|------|------|
| `/health` | GET | 健康檢查 |
| `/v1/audio/transcriptions` | POST | 同步轉錄（OpenAI 相容） |
| `/v1/audio/transcriptions/stream` | POST | 串流轉錄（SSE 進度） |
| `/ws/transcribe` | WebSocket | 即時串流轉錄 |
| `/docs` | GET | Swagger API 文檔 |

---

### 1. 同步轉錄 API

**適用場景**：短音訊（< 5 分鐘）

```bash
curl -X POST http://localhost:8189/v1/audio/transcriptions \
  -F "file=@audio.wav" \
  -F "language=auto" \
  -F "hotwords=人工智慧,機器學習" \
  -F "itn=true"
```

**參數說明**：

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `file` | File | 必填 | 音訊檔案 |
| `language` | string | `auto` | 語言：auto, zh, en, ja |
| `hotwords` | string | `""` | 熱詞，逗號分隔 |
| `itn` | bool | `true` | 是否啟用文字規整 |

**回應**：
```json
{
  "text": "識別出的文字內容...",
  "duration": 0.771,
  "audio_duration": 5.62
}
```

---

### 2. 串流轉錄 API（推薦用於長音訊）

**適用場景**：長音訊，需要即時進度回饋

```bash
curl -X POST http://localhost:8189/v1/audio/transcriptions/stream \
  -F "file=@long_audio.mp3" \
  -F "language=zh" \
  --no-buffer
```

**回應格式**：Server-Sent Events (SSE)

```
data: {"type": "progress", "current": 1, "total": 33, "text": "部分文字..."}
data: {"type": "progress", "current": 2, "total": 33, "text": "更多文字..."}
...
data: {"type": "complete", "text": "完整識別結果...", "duration": 39.191}
```

**事件類型**：

| type | 說明 | 欄位 |
|------|------|------|
| `progress` | 處理進度 | `current`, `total`, `text`（部分結果） |
| `complete` | 處理完成 | `text`（完整結果）, `duration` |

---

### 3. Python 客戶端範例

#### 同步呼叫

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

#### 串流呼叫（帶進度）

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
                    print(f"進度: {data['current']}/{data['total']}")
                elif data["type"] == "complete":
                    return data["text"]
    return None

text = transcribe_with_progress("long_audio.mp3", "zh")
print(text)
```

---

## 📊 效能基準

**測試環境**：NVIDIA L40S GPU

| 音訊時長 | VAD 分段 | 處理時間 | RTF |
|----------|----------|----------|-----|
| 3 秒 | 1 段 | 0.44s | 0.15x |
| 5 秒 | 1 段 | 0.77s | 0.15x |
| 6 分鐘 | 33 段 | 39s | 0.11x |
| 2 小時 | ~660 段 | ~13 分鐘 | ~0.11x |

> RTF (Real-Time Factor) < 1.0 表示處理速度快於即時播放

### VAD 分段機制

- 音訊 ≤ 30 秒：直接識別
- 音訊 > 30 秒：自動使用 FSMN-VAD 分段後逐段識別，避免幻覺

---

## 🗣️ 支援的語言

### 主要語言
中文、英語、日語、韓語、德語、西班牙語、法語、義大利語、俄語

### 中文方言
粵語、四川話、東北話、上海話、閩南語等 18 種方言

### 特殊能力
- 高噪音環境識別
- 歌詞識別
- 熱詞增強
- ITN 文字規整

---

## 📋 更新日誌

| 版本 | 日期 | 更新內容 |
|------|------|----------|
| v1.3.1 | 2024-12-18 | 非同步 API + UI 進度條 + SSE 串流端點 |
| v1.1.0 | 2024-12-18 | VAD 分段支援長音訊 |
| v1.0.0 | 2024-12-18 | 初始版本 |

---

## 🛠️ 技術棧

- **ASR 模型**：[Fun-ASR-Nano-2512](https://huggingface.co/FunAudioLLM/Fun-ASR-Nano-2512)
- **VAD 模型**：[FSMN-VAD](https://modelscope.cn/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch)
- **框架**：FastAPI + Gradio
- **執行環境**：PyTorch + CUDA 12.1
- **容器**：Docker + NVIDIA Container Toolkit

---

## 📄 授權條款

本專案採用 Apache License 2.0 授權 - 詳見 [LICENSE](LICENSE) 檔案。

---

## 🙏 致謝

- [FunAudioLLM/Fun-ASR](https://github.com/FunAudioLLM/Fun-ASR) - Fun-ASR-Nano 模型
- [阿里巴巴達摩院](https://github.com/alibaba-damo-academy/FunASR) - FunASR 框架

---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=neosun100/fun-asr-docker&type=Date)](https://star-history.com/#neosun100/fun-asr-docker)

---

## 📱 關注公眾號

![公眾號](https://img.aws.xin/uPic/扫码_搜索联合传播样式-标准色版.png)
