import os
import json
import threading
import time
from pathlib import Path
from flask import Flask, request, render_template, send_file, abort, url_for, jsonify

from faster_whisper import WhisperModel
from pyannote.audio import Pipeline
from pyannote.core import Segment
import torch
import uuid

APP_DIR = Path(__file__).parent.resolve()
UPLOAD_DIR = APP_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)

KEEP_UPLOADS = os.environ.get("KEEP_UPLOADS", "false").lower() == "true"

# Load token from config.json
config_path = os.path.join(APP_DIR, "config.json")
with open(config_path, "r") as f:
    config = json.load(f)
HF_TOKEN = config.get("HUGGINGFACE_HUB_TOKEN", "").strip()

# Load models once at startup
model = WhisperModel("base.en", device="cpu", compute_type="int8")
try:
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=HF_TOKEN
    )
    if torch.cuda.is_available():
        pipeline.to(torch.device("cuda"))
    print("Pyannote pipeline loaded successfully")
except Exception as e:
    print(f"Failed to load pyannote pipeline: {e}")
    pipeline = None

# Global dict for task status (simple in-memory; use Redis for production)
tasks = {}

def overlaps(segment_a, segment_b, threshold=0.5):
    """Check temporal overlap between segments."""
    start_a, end_a = segment_a.start, segment_a.end
    start_b, end_b = segment_b.start, segment_b.end
    overlap_start = max(start_a, start_b)
    overlap_end = min(end_a, end_b)
    overlap_duration = max(0, overlap_end - overlap_start)
    min_duration = min(end_a - start_a, end_b - start_b)
    return (overlap_duration / min_duration) > threshold if min_duration > 0 else False

def cleanup_uploads(exclude_files=None):
    """Delete old files in UPLOAD_DIR, excluding specified files."""
    exclude_files = exclude_files or set()
    for file_path in UPLOAD_DIR.iterdir():
        if file_path.name not in exclude_files and file_path.is_file():
            try:
                file_path.unlink(missing_ok=True)
            except Exception as e:
                print(f"Failed to delete {file_path}: {e}")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "file" not in request.files:
            return render_template("index.html", error="No file part")
        f = request.files["file"]
        if not f or f.filename == "":
            return render_template("index.html", error="No file selected")
        if not f.filename.lower().endswith((".mp3", ".wav", ".flac", ".m4a", ".ogg")):
            return render_template("index.html", error="Unsupported format. Use MP3, WAV, FLAC, M4A, or OGG.")

        # Clean old uploads before saving new one
        cleanup_uploads()

        # Persist upload
        suffix = os.path.splitext(f.filename)[1]
        tmp_path = UPLOAD_DIR / f"upload{suffix}"
        f.save(tmp_path)

        # Create task ID
        task_id = str(uuid.uuid4())
        tasks[task_id] = {
            "status": "received",
            "message": "File received, starting transcription...",
            "segments": None
        }

        # Start background processing
        threading.Thread(target=process_audio, args=(task_id, str(tmp_path))).start()

        return render_template("index.html", task_id=task_id, status="processing")

    return render_template("index.html")

def process_audio(task_id, tmp_path):
    try:
        tasks[task_id]["status"] = "transcribing"
        tasks[task_id]["message"] = "Transcribing audio..."
        # Transcribe with timestamps
        segments, info = model.transcribe(tmp_path, beam_size=5)
        lang = info.language
        tasks[task_id]["status"] = "diarizing"
        tasks[task_id]["message"] = "Identifying speakers..."
        # Diarization (if pipeline loaded)
        if pipeline:
            waveform, sample_rate = torchaudio.load(tmp_path)
            diarization = pipeline({"waveform": waveform, "sample_rate": sample_rate})
            # Align speakers to segments
            formatted_segments = []
            for segment in segments:
                best_speaker = None
                max_overlap = 0
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    turn_segment = Segment(turn.start, turn.end)
                    overlap_ratio = overlaps(segment, turn_segment)
                    if overlap_ratio > max_overlap:
                        max_overlap = overlap_ratio
                        best_speaker = speaker
                # Format timestamp as MM:SS
                start_min, start_sec = divmod(int(segment.start), 60)
                end_min, end_sec = divmod(int(segment.end), 60)
                timestamp = f"[{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}]"
                speaker_label = f"SPEAKER_{best_speaker}" if best_speaker else "UNKNOWN"
                formatted_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "speaker": speaker_label,
                    "text": segment.text.strip()
                })
        else:
            # Fallback without diarization
            formatted_segments = []
            for segment in segments:
                start_min, start_sec = divmod(int(segment.start), 60)
                end_min, end_sec = divmod(int(segment.end), 60)
                timestamp = f"[{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}]"
                formatted_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "speaker": "UNKNOWN",
                    "text": segment.text.strip()
                })
        tasks[task_id]["status"] = "complete"
        tasks[task_id]["message"] = "Processing complete!"
        tasks[task_id]["segments"] = formatted_segments
        tasks[task_id]["lang"] = lang
    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["message"] = f"Error: {str(e)}"

@app.route("/status/<task_id>")
def status(task_id):
    task = tasks.get(task_id, {"status": "not_found", "message": "Task not found"})
    return jsonify(task)

@app.route("/result/<task_id>")
def result(task_id):
    task = tasks.get(task_id)
    if task and task["status"] == "complete":
        return render_template(
            "result.html",
            lang=task["lang"],
            segments=task["segments"],
            files={
                "txt": url_for('download_file', kind='txt', task_id=task_id),
                "json": url_for('download_file', kind='json', task_id=task_id),
                "srt": url_for('download_file', kind='srt', task_id=task_id),
                "vtt": url_for('download_file', kind='vtt', task_id=task_id),
            },
            audio_url=url_for('serve_audio', filename=f"upload_{task_id}{suffix}") if KEEP_UPLOADS else None
        )
    else:
        return render_template("index.html", error=task.get("message", "Processing not complete"))

def to_srt(segments):
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{seg['start']:.3f} --> {seg['end']:.3f}")
        lines.append(f"{seg['speaker']}: {seg['text']}")
        lines.append("")
    return "\n".join(lines)

def to_vtt(segments):
    lines = ["WEBVTT", ""]
    for seg in segments:
        lines.append(f"{seg['start']:.3f} --> {seg['end']:.3f}")
        lines.append(f"{seg['speaker']}: {seg['text']}")
        lines.append("")
    return "\n".join(lines)

@app.route("/download/<kind>/<task_id>")
def download_file(kind: str, task_id: str):
    task = tasks.get(task_id)
    if not task or task["status"] != "complete":
        abort(404)
    base = "transcription"
    path = UPLOAD_DIR / f"{base}_{task_id}.{kind}"
    if not path.exists():
        abort(404)
    return send_file(str(path), as_attachment=True, download_name=path.name)

@app.route("/audio/<task_id>/<suffix>")
def serve_audio(task_id: str, suffix: str):
    path = UPLOAD_DIR / f"upload_{task_id}{suffix}"
    if not path.exists():
        abort(404)
    return send_file(str(path), mimetype='audio/mpeg' if suffix.endswith('.mp3') else 'audio/wav')

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=False, host=host, port=port)