[English](README.md) | [简体中文](README_CN.md) | [繁體中文](README_TW.md) | [日本語](README_JP.md)

<div align="center">

# 🎙️ Fun-ASR All-in-One Docker

[![Docker Pulls](https://img.shields.io/docker/pulls/neosun/fun-asr?style=flat-square&logo=docker)](https://hub.docker.com/r/neosun/fun-asr)
[![Docker Image Version](https://img.shields.io/docker/v/neosun/fun-asr?style=flat-square&logo=docker&sort=semver)](https://hub.docker.com/r/neosun/fun-asr)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=flat-square)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/neosun100/fun-asr-docker?style=flat-square&logo=github)](https://github.com/neosun100/fun-asr-docker)

**Fun-ASR-Nano-2512 ベースの本番環境対応音声認識サービス**

Docker コマンド一つで Web UI + REST API + WebSocket + リアルタイム進捗を取得

[クイックスタート](#-クイックスタート) • [機能](#-機能) • [API ドキュメント](#-api-リファレンス) • [パフォーマンス](#-パフォーマンスベンチマーク)

</div>

---

## 📸 スクリーンショット

![Web UI](images/ui-screenshot.png)

---

## ✨ 機能

| 機能 | 説明 |
|------|------|
| 🎯 **Fun-ASR-Nano-2512** | Alibaba 通義実験室の最新 800M パラメータ E2E ASR モデル |
| 🔊 **VAD 自動分割** | 30 秒以上の音声を自動分割、ハルシネーション防止 |
| 📊 **リアルタイム進捗** | UI プログレスバー + SSE ストリーミング API |
| 🔌 **OpenAI 互換** | `/v1/audio/transcriptions` Whisper API 互換 |
| 🌍 **多言語対応** | 31 言語、7 種類の中国語方言、26 種類の地方アクセント |
| ⚡ **高性能** | RTF < 0.1、6 分の音声を約 40 秒で処理 |

---

## 🚀 クイックスタート

```bash
docker run -d \
  --name fun-asr \
  --gpus '"device=0"' \
  -p 8189:8189 \
  -v fun-asr-models:/root/.cache \
  neosun/fun-asr:latest
```

初回起動時はモデルをダウンロード（約 1.8GB）、以降はキャッシュから読み込み（約 30 秒）。

http://localhost:8189 を開いて使用開始 🎉

---

## 📦 インストール

### 前提条件

- Docker 20.10+
- NVIDIA GPU（VRAM 4GB+）
- NVIDIA Container Toolkit

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

### ヘルスチェック

```bash
curl http://localhost:8189/health
# {"status":"healthy","model_loaded":true,"vad_loaded":true,"gpu":{...}}
```

---

## ⚙️ 設定

### 環境変数

| 変数 | デフォルト | 説明 |
|------|------------|------|
| `PORT` | `8189` | サービスポート |
| `MODEL_DIR` | `FunAudioLLM/Fun-ASR-Nano-2512` | モデルパス |

### ボリューム

| パス | 説明 |
|------|------|
| `/root/.cache` | モデルキャッシュ（永続化） |

---

## 🖥️ Web UI

http://localhost:8189 にアクセスして Web インターフェースを使用：

### 機能
- 📤 音声ファイルのアップロード（wav, mp3, m4a, flac など対応）
- 🎤 リアルタイム録音認識
- 📊 **プログレスバー**（長い音声の分割処理時にリアルタイム更新）
- ⚙️ 設定：言語、ホットワード、ITN

### 出力情報
```
⏱️ 認識時間: 39.19s | 音声長: 367.96s | RTF: 0.11x | VAD分割: 33セグメント
```

---

## 📡 API リファレンス

### エンドポイント一覧

| エンドポイント | メソッド | 説明 |
|----------------|----------|------|
| `/health` | GET | ヘルスチェック |
| `/v1/audio/transcriptions` | POST | 同期転写（OpenAI 互換） |
| `/v1/audio/transcriptions/stream` | POST | ストリーミング転写（SSE 進捗） |
| `/ws/transcribe` | WebSocket | リアルタイムストリーミング |
| `/docs` | GET | Swagger UI |

---

### 1. 同期転写 API

**適用シーン**：短い音声（< 5 分）

```bash
curl -X POST http://localhost:8189/v1/audio/transcriptions \
  -F "file=@audio.wav" \
  -F "language=auto" \
  -F "hotwords=人工知能,機械学習" \
  -F "itn=true"
```

**パラメータ**：

| パラメータ | 型 | デフォルト | 説明 |
|------------|------|------------|------|
| `file` | File | 必須 | 音声ファイル |
| `language` | string | `auto` | 言語：auto, zh, en, ja |
| `hotwords` | string | `""` | ホットワード（カンマ区切り） |
| `itn` | bool | `true` | テキスト正規化を有効化 |

**レスポンス**：
```json
{
  "text": "認識されたテキスト...",
  "duration": 0.771,
  "audio_duration": 5.62
}
```

---

### 2. ストリーミング転写 API（長い音声に推奨）

**適用シーン**：長い音声、リアルタイム進捗が必要な場合

```bash
curl -X POST http://localhost:8189/v1/audio/transcriptions/stream \
  -F "file=@long_audio.mp3" \
  -F "language=ja" \
  --no-buffer
```

**レスポンス形式**：Server-Sent Events (SSE)

```
data: {"type": "progress", "current": 1, "total": 33, "text": "部分テキスト..."}
data: {"type": "progress", "current": 2, "total": 33, "text": "さらにテキスト..."}
...
data: {"type": "complete", "text": "完全な認識結果...", "duration": 39.191}
```

**イベントタイプ**：

| type | 説明 | フィールド |
|------|------|------------|
| `progress` | 処理進捗 | `current`, `total`, `text`（部分結果） |
| `complete` | 処理完了 | `text`（完全結果）, `duration` |

---

### 3. Python クライアント例

#### 同期呼び出し

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

result = transcribe("audio.wav", "ja")
print(result["text"])
```

#### ストリーミング呼び出し（進捗付き）

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
                    print(f"進捗: {data['current']}/{data['total']}")
                elif data["type"] == "complete":
                    return data["text"]
    return None

text = transcribe_with_progress("long_audio.mp3", "ja")
print(text)
```

---

## 📊 パフォーマンスベンチマーク

**テスト環境**：NVIDIA L40S GPU

| 音声長 | VAD 分割 | 処理時間 | RTF |
|--------|----------|----------|-----|
| 3 秒 | 1 セグメント | 0.44s | 0.15x |
| 5 秒 | 1 セグメント | 0.77s | 0.15x |
| 6 分 | 33 セグメント | 39s | 0.11x |
| 2 時間 | ~660 セグメント | ~13 分 | ~0.11x |

> RTF (Real-Time Factor) < 1.0 はリアルタイム再生より高速

### VAD 分割メカニズム

- 音声 ≤ 30 秒：直接認識
- 音声 > 30 秒：FSMN-VAD で自動分割後、セグメントごとに認識（ハルシネーション防止）

---

## 🗣️ 対応言語

### 主要言語
中国語、英語、日本語、韓国語、ドイツ語、スペイン語、フランス語、イタリア語、ロシア語

### 中国語方言
広東語、四川語、東北語、上海語、閩南語など 18 種類

### 特殊機能
- 高ノイズ環境認識
- 歌詞認識
- ホットワードブースト
- ITN テキスト正規化

---

## 📋 更新履歴

| バージョン | 日付 | 変更内容 |
|------------|------|----------|
| v1.2.0 | 2024-12-18 | 非同期 API + UI プログレスバー + SSE ストリーミング |
| v1.1.0 | 2024-12-18 | VAD 分割で長い音声に対応 |
| v1.0.0 | 2024-12-18 | 初期リリース |

---

## 🛠️ 技術スタック

- **ASR モデル**：[Fun-ASR-Nano-2512](https://huggingface.co/FunAudioLLM/Fun-ASR-Nano-2512)
- **VAD モデル**：[FSMN-VAD](https://modelscope.cn/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch)
- **フレームワーク**：FastAPI + Gradio
- **ランタイム**：PyTorch + CUDA 12.1
- **コンテナ**：Docker + NVIDIA Container Toolkit

---

## 📄 ライセンス

このプロジェクトは Apache License 2.0 の下でライセンスされています - 詳細は [LICENSE](LICENSE) ファイルを参照。

---

## 🙏 謝辞

- [FunAudioLLM/Fun-ASR](https://github.com/FunAudioLLM/Fun-ASR) - Fun-ASR-Nano モデル
- [Alibaba DAMO Academy](https://github.com/alibaba-damo-academy/FunASR) - FunASR フレームワーク

---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=neosun100/fun-asr-docker&type=Date)](https://star-history.com/#neosun100/fun-asr-docker)

---

## 📱 公式アカウント

![WeChat](https://img.aws.xin/uPic/扫码_搜索联合传播样式-标准色版.png)
