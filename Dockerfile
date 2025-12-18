FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3.10-venv \
    ffmpeg \
    libsndfile1 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.10 /usr/bin/python

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121 && \
    pip install -r requirements.txt

# Copy application code
COPY model.py .
COPY app.py .
COPY mcp_server.py .

# ============================================
# ALL-IN-ONE: Pre-download models during build
# ============================================

# Download Fun-ASR-Nano-2512 model from ModelScope
RUN python -c "from funasr import AutoModel; \
    AutoModel(model='FunAudioLLM/Fun-ASR-Nano-2512', \
              trust_remote_code=True, \
              remote_code='./model.py', \
              device='cpu', \
              disable_update=True)" && \
    echo "ASR model downloaded successfully"

# Download FSMN-VAD model from ModelScope
RUN python -c "from funasr import AutoModel; \
    AutoModel(model='fsmn-vad', \
              model_revision='v2.0.4', \
              device='cpu', \
              disable_update=True)" && \
    echo "VAD model downloaded successfully"

# Expose port
EXPOSE 8189

# Health check (reduced start-period since models are pre-loaded)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8189/health || exit 1

# Start command
CMD ["python", "app.py"]
