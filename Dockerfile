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

# Copy model.py first (needed for ASR model loading)
COPY model.py .

# ============================================
# ALL-IN-ONE: Pre-download models during build
# These layers are cached, won't re-download unless model.py changes
# ============================================

# Download Fun-ASR-Nano-2512 model (1.84GB)
RUN python -c "from funasr import AutoModel; \
    AutoModel(model='FunAudioLLM/Fun-ASR-Nano-2512', \
              trust_remote_code=True, \
              remote_code='./model.py', \
              device='cpu', \
              disable_update=True)" && \
    echo "ASR model downloaded successfully"

# Download FSMN-VAD model (1.6MB)
RUN python -c "from funasr import AutoModel; \
    AutoModel(model='fsmn-vad', \
              model_revision='v2.0.4', \
              device='cpu', \
              disable_update=True)" && \
    echo "VAD model downloaded successfully"

# Copy application code AFTER model download (changes here won't invalidate model cache)
COPY app.py .
COPY mcp_server.py .

# Expose port
EXPOSE 8189

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8189/health || exit 1

# Start command
CMD ["python", "app.py"]
