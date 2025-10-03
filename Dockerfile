# Stage 1: Builder (install deps)
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y ffmpeg git && rm -rf /var/lib/apt/lists/*
WORKDIR /builder
COPY requirements.txt .
COPY config.json .
COPY download_vad.py .
RUN pip install --user --no-cache-dir -r requirements.txt
# Pre-download silero VAD model with token
RUN mkdir -p /root/.cache/whisperx-vad && \
    python download_vad.py

# Stage 2: Runtime (copy from builder)
FROM python:3.11-slim
# Install runtime FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
# Copy installed deps and VAD model from builder
COPY --from=builder /root/.local /root/.local
COPY --from=builder /root/.cache/whisperx-vad /root/.cache/whisperx-vad
ENV PATH=/root/.local/bin:$PATH
# Labels for versioning/backup
LABEL maintainer="leon@americaschoicetax.com" \
      version="1.0" \
      description="Quick audio transcription app with speaker diarization" \
      org.opencontainers.image.source="https://github.com/provecticus/docker-transcribe-app"
WORKDIR /app
COPY app.py asr_pipeline.py config.json ./
COPY templates/ ./templates/
RUN mkdir uploads
EXPOSE 5000
CMD ["python", "app.py"]
