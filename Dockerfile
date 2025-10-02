FROM python:3.11-slim

# Install FFmpeg (for MP3/WAV)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Install Python deps (wheels for 3.11)
RUN pip install --no-cache-dir flask faster-whisper==1.0.3

# App setup
WORKDIR /app
COPY app.py ./
COPY templates/ ./templates/
RUN mkdir uploads

EXPOSE 5000
CMD ["python", "app.py"]