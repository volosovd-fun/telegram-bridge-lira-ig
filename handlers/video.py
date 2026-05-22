"""Video handler — Gemini 2.5 Flash video input.

Telegram getFile limited to 20MB. Anything larger → reject.
Gemini accepts mp4, mov, avi, etc inline (base64) up to certain size limits.
"""

import os
import base64
import logging
import requests

log = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

# Telegram Bot API limit: getFile up to 20MB
MAX_VIDEO_BYTES = 20 * 1024 * 1024

PROMPT_VIDEO = """Опиши це відео українською. ≤300 слів.
Розкажи:
1. Що відбувається візуально (загальний контекст, головні кадри)
2. Що говорять (основна мова з аудіо, ключові фрази)
3. Якщо це reel/short — стиль, hook, CTA, тон

Без преамбули, одразу опис.
"""


def analyze(video_bytes: bytes, mime: str = "video/mp4", duration_seconds: float = 0) -> dict:
    """Analyze video via Gemini 2.5 Flash.

    Returns:
        {"description": str, "duration": float} on success
        {"error": str} on failure
    """
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured"}

    if len(video_bytes) > MAX_VIDEO_BYTES:
        return {"error": "video too large (>20MB Telegram Bot API limit)"}

    b64 = base64.b64encode(video_bytes).decode("utf-8")
    payload = {
        "contents": [{
            "parts": [
                {"text": PROMPT_VIDEO},
                {"inline_data": {"mime_type": mime, "data": b64}},
            ]
        }]
    }

    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
            timeout=180,  # video analysis can be slow
        )
        resp.raise_for_status()
        result = resp.json()
        candidates = result.get("candidates", [])
        if not candidates:
            return {"error": "empty candidates"}
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            return {"error": "empty text"}
        return {"description": text, "duration": duration_seconds}
    except requests.HTTPError as e:
        log.error(f"[video] HTTP {e.response.status_code}: {e.response.text[:200]}")
        return {"error": f"HTTP {e.response.status_code}"}
    except requests.RequestException as e:
        log.error(f"[video] request failed: {e}")
        return {"error": str(e)}


def format_video_prefix(description: str, duration_seconds: float, is_video_note: bool = False) -> str:
    label = "кружечок" if is_video_note else "відео"
    if duration_seconds > 0:
        mins = int(duration_seconds) // 60
        secs = int(duration_seconds) % 60
        duration_str = f" {mins}:{secs:02d}"
    else:
        duration_str = ""
    return f"[{label}{duration_str}]: {description}"
