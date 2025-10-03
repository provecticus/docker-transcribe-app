import os
import json
from pathlib import Path
from flask import Flask, request, render_template, send_file, abort, url_for

from asr_pipeline import transcribe_with_speakers, to_srt, to_vtt

APP_DIR = Path(__file__).parent.resolve()
UPLOAD_DIR = APP_DIR / "Uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small.en")
KEEP_UPLOADS = os.environ.get("KEEP_UPLOADS", "false").lower() == "true"

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

        try:
            res = transcribe_with_speakers(str(tmp_path), model_name=WHISPER_MODEL)
            segments = res["segments"]
            lang = res["language"]

            base = "transcription"
            json_path = UPLOAD_DIR / f"{base}.json"
            srt_path = UPLOAD_DIR / f"{base}.srt"
            vtt_path = UPLOAD_DIR / f"{base}.vtt"
            txt_path = UPLOAD_DIR / f"{base}.txt"

            json_path.write_text(json.dumps({"language": lang, "segments": segments}, ensure_ascii=False, indent=2), encoding="utf-8")
            srt_path.write_text(to_srt(segments), encoding="utf-8")
            vtt_path.write_text(to_vtt(segments), encoding="utf-8")

            # Human-readable TXT
            lines = []
            for seg in segments:
                mm_start = int(seg["start"] // 60)
                ss_start = int(seg["start"] % 60)
                mm_end = int(seg["end"] // 60)
                ss_end = int(seg["end"] % 60)
                lines.append(f"[{mm_start:02d}:{ss_start:02d} - {mm_end:02d}:{ss_end:02d}] {seg['speaker']}: {seg['text']}")
            txt_path.write_text("\n".join(lines), encoding="utf-8")

            # Keep audio file and generate URL
            audio_url = url_for('serve_audio', filename=f"upload{suffix}") if KEEP_UPLOADS else None

            # Delete original upload (if not keeping)
            if not KEEP_UPLOADS:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass

            return render_template(
                "result.html",
                lang=lang,
                segments=segments,
                files={
                    "txt": url_for('download_file', kind='txt'),
                    "json": url_for('download_file', kind='json'),
                    "srt": url_for('download_file', kind='srt'),
                    "vtt": url_for('download_file', kind='vtt'),
                },
                audio_url=audio_url
            )

        except Exception as e:
            if not KEEP_UPLOADS:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
            return render_template("index.html", error=f"Transcription failed: {str(e)}")

    return render_template("index.html")

@app.route("/download/<kind>")
def download_file(kind: str):
    base = "transcription"
    if kind not in {"txt", "json", "srt", "vtt"}:
        abort(404)
    path = UPLOAD_DIR / f"{base}.{kind}"
    if not path.exists():
        abort(404)
    return send_file(str(path), as_attachment=True, download_name=path.name)

@app.route("/audio/<filename>")
def serve_audio(filename: str):
    path = UPLOAD_DIR / filename
    if not path.exists():
        abort(404)
    return send_file(str(path), mimetype='audio/mpeg' if filename.endswith('.mp3') else 'audio/wav')

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=False, host=host, port=port)
