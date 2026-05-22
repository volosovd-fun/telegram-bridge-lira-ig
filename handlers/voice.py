"""Voice message handler — ElevenLabs Scribe v2 transcription.

Reference: Lira-IG `app/stt.py` on VPS at /root/lira-ig-webhook/app/stt.py.
For V1 we re-implement minimally. Port full version on first deploy.
"""

import os
import logging
import requests

log = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/speech-to-text"


def transcribe(audio_bytes: bytes, mime: str = "audio/ogg") -> dict:
    """Transcribe audio via ElevenLabs Scribe v2 (Ukrainian).

    Returns:
        {"transcript": str, "duration": float} on success
        {"error": str} on failure
    """
    if not ELEVENLABS_API_KEY:
        return {"error": "ELEVENLABS_API_KEY not configured"}

    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    files = {
        "file": ("audio.oga", audio_bytes, mime),
    }
    data = {
        "model_id": "scribe_v1",
        "language_code": "uk",
    }

    try:
        resp = requests.post(ELEVENLABS_URL, headers=headers, files=files, data=data, timeout=90)
        resp.raise_for_status()
        result = resp.json()
        transcript = result.get("text", "").strip()
        duration = result.get("duration_seconds") or result.get("duration", 0)
        if not transcript:
            return {"error": "empty transcript"}
        return {"transcript": transcript, "duration": float(duration)}
    except requests.HTTPError as e:
        log.error(f"[stt] HTTP {e.response.status_code}: {e.response.text[:200]}")
        return {"error": f"HTTP {e.response.status_code}"}
    except requests.RequestException as e:
        log.error(f"[stt] request failed: {e}")
        return {"error": str(e)}


def format_voice_prefix(transcript: str, duration_seconds: float) -> str:
    """Format as `[голосове 0:30]: {transcript}` for prefix injection."""
    mins = int(duration_seconds) // 60
    secs = int(duration_seconds) % 60
    duration_str = f"{mins}:{secs:02d}"
    return f"[голосове {duration_str}]: {transcript}"
