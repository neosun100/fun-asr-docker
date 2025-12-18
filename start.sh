#!/bin/bash
set -e

echo "🎙️ Fun-ASR Docker Launcher"
echo "=========================="

# Check nvidia-docker
if ! command -v nvidia-smi &> /dev/null; then
    echo "❌ nvidia-smi not found. Please install NVIDIA drivers."
    exit 1
fi

if ! docker info 2>/dev/null | grep -q "Runtimes.*nvidia"; then
    echo "⚠️  nvidia-docker runtime not detected, but may still work with --gpus flag"
fi

# Auto-select GPU with least memory usage
echo "🔍 Detecting GPUs..."
GPU_ID=$(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits | \
         sort -t',' -k2 -n | head -1 | cut -d',' -f1 | tr -d ' ')

if [ -z "$GPU_ID" ]; then
    echo "❌ No GPU detected"
    exit 1
fi

GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader --id=$GPU_ID)
GPU_MEM=$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader --id=$GPU_ID)
echo "✅ Selected GPU $GPU_ID: $GPU_NAME ($GPU_MEM)"

# Set environment
export NVIDIA_VISIBLE_DEVICES=$GPU_ID
export PORT=${PORT:-8189}

# Load .env if exists
if [ -f .env ]; then
    echo "📄 Loading .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Check port availability
if ss -tlnp | grep -q ":$PORT "; then
    echo "❌ Port $PORT is already in use"
    exit 1
fi

echo ""
echo "🚀 Starting Fun-ASR service..."
echo "   GPU: $GPU_ID"
echo "   Port: $PORT"
echo ""

# Start with docker-compose
docker compose up -d

echo ""
echo "✅ Fun-ASR is starting!"
echo ""
echo "📍 Access points:"
echo "   Web UI:    http://localhost:$PORT"
echo "   API Docs:  http://localhost:$PORT/docs"
echo "   WebSocket: ws://localhost:$PORT/ws/transcribe"
echo ""
echo "📋 Commands:"
echo "   View logs:  docker logs -f fun-asr"
echo "   Stop:       docker compose down"
echo ""
