"""ElevenLabs TTS — synthesize text → OGG OPUS for Telegram sendVoice.

Telegram's sendVoice expects an OGG/OPUS file (mime audio/ogg) for proper
voice-note rendering. ElevenLabs supports `opus_48000_128` natively, so we
skip ffmpeg.
"""

import os
import logging
from typing import Optional

import requests

log = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID")
ELEVENLABS_TTS_MODEL = os.environ.get("ELEVENLABS_TTS_MODEL", "eleven_multilingual_v2")

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
OUTPUT_FORMAT = "opus_48000_128"
TIMEOUT_SECONDS = 60
MAX_CHARS = 2500  # ~150s of voice — sane upper bound


def synthesize(text: str) -> Optional[bytes]:
    """Render `text` through ElevenLabs and return OGG OPUS bytes, or None."""
    if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
        log.error("[tts] missing ELEVENLABS_API_KEY or ELEVENLABS_VOICE_ID — skipping")
        return None

    clipped = text.strip()[:MAX_CHARS]
    if not clipped:
        log.warning("[tts] empty text — skipping")
        return None

    url = API_URL.format(voice_id=ELEVENLABS_VOICE_ID)
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/ogg",
    }
    payload = {
        "text": clipped,
        "model_id": ELEVENLABS_TTS_MODEL,
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.75,
            "style": 0.55,
            "use_speaker_boost": True,
        },
    }
    try:
        resp = requests.post(
            url,
            headers=headers,
            json=payload,
            params={"output_format": OUTPUT_FORMAT},
            timeout=TIMEOUT_SECONDS,
        )
        if resp.status_code >= 400:
            log.warning(f"[tts] HTTP {resp.status_code}: {resp.text[:300]}")
            return None
        log.info(f"[tts] ok voice={ELEVENLABS_VOICE_ID} chars={len(clipped)} bytes={len(resp.content)}")
        return resp.content
    except requests.RequestException as e:
        log.error(f"[tts] request failed: {e}")
        return None
