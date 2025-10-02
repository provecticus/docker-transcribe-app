# Stage 1: Builder (install deps)
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y ffmpeg git && rm -rf /var/lib/apt/lists/*

WORKDIR /builder
RUN pip install --user --no-cache-dir flask faster-whisper==1.0.3

# Stage 2: Runtime (copy from builder)
FROM python:3.11-slim

# Install runtime FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy installed deps from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Labels for versioning/backup
LABEL maintainer="your-team@company.com" \
      version="1.0" \
      description="Quick audio transcription app" \
      org.opencontainers.image.source="https://github.com/your-repo/transcribe-app"

WORKDIR /app
COPY app.py ./
COPY templates/ ./templates/
RUN mkdir uploads

EXPOSE 5000
CMD ["python", "app.py"]