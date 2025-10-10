import os
import json
from datetime import timedelta
import torch
import whisperx
from huggingface_hub import login, hf_hub_download
import shutil

def fmt_clock(seconds: float | None) -> str:
    if seconds is None:
        return "--:--"
    ms = int(seconds * 1000)
    h = ms // 3_600_000
    ms -= h * 3_600_000
    m = ms // 60_000
    ms -= m * 60_000
    s = ms // 1_000
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def transcribe_with_speakers(audio_path: str, model_name: str = "small.en", device: str | None = None):
    """
    Transcribe and diarize audio using WhisperX + pyannote.
    Returns:
      {
        "language": str,
        "segments": [ { "start": float, "end": float, "speaker": str, "text": str }, ... ]
      }
    """
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    compute_type = "float16" if device == "cuda" else "int8"

    # Load token from config.json
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        hf_token = config.get("HUGGINGFACE_HUB_TOKEN", "").strip()
    except FileNotFoundError:
        raise RuntimeError("config.json not found. Create it with HUGGINGFACE_HUB_TOKEN.")
    if not hf_token:
        raise RuntimeError("HUGGINGFACE_HUB_TOKEN is not set in config.json.")

    # Log in to Hugging Face
    try:
        login(token=hf_token)
        print("Successfully logged in to Hugging Face")
    except Exception as e:
        raise RuntimeError(f"Failed to authenticate with Hugging Face: {str(e)}")

    # Clear VAD cache to fix checksum mismatch
    vad_cache_path = "/root/.cache/torch/whisperx-vad-segmentation.bin"
    if os.path.exists(vad_cache_path):
        print("Clearing VAD cache to fix checksum mismatch")
        os.remove(vad_cache_path)

    # Ensure VAD model is available
    vad_model_path = "/root/.cache/whisperx-vad/silero_vad.onnx"
    if not os.path.exists(vad_model_path):
        try:
            print("Downloading silero VAD model")
            os.makedirs("/root/.cache/whisperx-vad", exist_ok=True)
            downloaded_file = hf_hub_download(repo_id="onnx-community/silero-vad", filename="onnx/model_int8.onnx", local_dir="/root/.cache/whisperx-vad", token=hf_token)
            shutil.move(downloaded_file, vad_model_path)
        except Exception as e:
            raise RuntimeError(f"Failed to download VAD model: {str(e)}")

    # 1) ASR transcription with timestamps
    try:
        print(f"Loading WhisperX model: {model_name}")
        model = whisperx.load_model(model_name, device, compute_type=compute_type, vad_options={"model_fp": vad_model_path})
    except Exception as e:
        raise RuntimeError(f"Failed to load WhisperX model {model_name}: {str(e)}")
    try:
        audio = whisperx.load_audio(audio_path)
        asr = model.transcribe(audio, batch_size=16 if device == "cuda" else 8)
        language = asr.get("language", "en")
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {str(e)}")

    # 2) Alignment for better timing
    try:
        print("Loading alignment model")
        model_a, metadata = whisperx.load_align_model(language_code=language, device=device)
        asr_aligned = whisperx.align(asr["segments"], model_a, metadata, audio, device)
    except Exception as e:
        raise RuntimeError(f"Alignment failed: {str(e)}")

    # 3) Diarize
    try:
        print("Loading diarization pipeline")
        diarize_model = whisperx.DiarizationPipeline(use_auth_token=hf_token, device=device)
        diar = diarize_model(audio)
        print(f"Diarization output: {diar}")
    except Exception as e:
        raise RuntimeError(f"Diarization failed: {str(e)}")
    dsegs = diar.get("segments", [])

    # 4) Assign a speaker to each ASR segment
    results = []
    for seg in asr_aligned["segments"]:
        s_start, s_end = seg["start"], seg["end"]
        best_spk, best_overlap = "Speaker ?", 0.0
        for d in dsegs:
            overlap = max(0.0, min(s_end, d["end"]) - max(s_start, d["start"]))
            if overlap > best_overlap:
                best_overlap = overlap
                best_spk = d["speaker"].replace("SPEAKER_", "Speaker ")
        results.append({
            "start": float(s_start),
            "end": float(s_end),
            "speaker": best_spk,
            "text": seg["text"].strip()
        })

    return {"language": language, "segments": results}

def to_srt(segments: list[dict]) -> str:
    def srt_ts(t: float) -> str:
        ms = int(t * 1000)
        h = ms // 3_600_000; ms -= h * 3_600_000
        m = ms // 60_000;    ms -= m * 60_000
        s = ms // 1_000;     ms -= s * 1_000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{srt_ts(seg['start'])} --> {srt_ts(seg['end'])}")
        lines.append(f"{seg['speaker']}: {seg['text']}")
        lines.append("")
    return "\n".join(lines)

def to_vtt(segments: list[dict]) -> str:
    def vtt_ts(t: float) -> str:
        ms = int(t * 1000)
        h = ms // 3_600_000; ms -= h * 3_600_000
        m = ms // 60_000;    ms -= m * 60_000
        s = ms // 1_000;     ms -= s * 1_000
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
    lines = ["WEBVTT", ""]
    for seg in segments:
        lines.append(f"{vtt_ts(seg['start'])} --> {vtt_ts(seg['end'])}")
        lines.append(f"{seg['speaker']}: {seg['text']}")
        lines.append("")
    return "\n".join(lines)