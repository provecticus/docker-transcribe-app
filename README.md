# Quick Transcription Web App

A minimal, Dockerized web app for uploading audio files (MP3, WAV, etc.) and transcribing them to text using faster-whisper. Built for rapid deployment—upload via browser, get instant text display + TXT download. CPU-optimized for speed (~10-30s per min audio).

## Features
- **Upload & Transcribe**: Supports MP3, WAV, FLAC, M4A, OGG.
- **Web UI**: Simple form; results show on-page with download.
- **Dockerized**: Portable, no local deps—runs anywhere with Docker.
- **Scalable**: Easy to spin up multiple instances (e.g., for load).

## Quick Start (Local Dev)
1. **Install Docker Desktop**: [Download here](https://www.docker.com/products/docker-desktop/). Restart PC after install.
2. **Clone & Build**:
git clone <your-repo-url>
cd transcribe-app
docker build -t transcribe-app .
3. **Run**:
docker run -d -p 5000:5000 --name transcribe-1 -v $(pwd)/uploads:/app/uploads transcribe-app
4. **Access**: `http://localhost:5000`. Upload audio → Transcribe → Download TXT.

## Usage
- Browse to `http://YOUR_IP:5000`.
- Select file → Submit → View text + "Download TXT".
- Logs: `docker logs transcribe-1 -f`.

## Scaling/Instances
- New instance: `docker run -d -p 5001:5000 --name transcribe-2 -v $(pwd)/uploads:/app/uploads transcribe-app`.
- Restart: `docker restart transcribe-1`.
- Stop: `docker stop transcribe-1 && docker rm transcribe-1`.

## Build History & Fixes
- **v1.0 (Oct 02, 2025)**: Initial Flask + faster-whisper on Python 3.11 (switched from 3.13 due to PyAV wheel issues).
- **Docker Tweaks**: Fixed COPY syntax (separate `COPY app.py ./` + `COPY templates/ ./templates/`) to avoid mis-placement.
- **Model**: "base.en" for speed; edit `app.py` to "small.en" for accuracy (slower).
- **First Run**: Downloads ~150MB model—needs internet.

## Troubleshooting
- **"No such file '/app/app.py'"**: Rebuild with `--no-cache`; check `docker run --rm transcribe-app ls -la /app/`.
- **Port in Use**: Use `-p 5001:5000`.
- **Slow Transcribe**: CPU-bound; add GPU later (`device="cuda"` in app.py + NVIDIA Docker).
- **Firewall**: Allow TCP 5000 inbound.
- **Logs Empty**: `docker logs transcribe-1` (model load takes 1-2 min first time).

## Deployment (Server)
See DEPLOYMENT.md for full guide.

## Next Steps
- Drag-drop UI (in progress).
- Folder monitoring (watchdog lib).
- Auth (Flask-Login).
- Integrate with KWVE repo (MinIO polling).

License: MIT. Built by Grok (xAI) + your team.