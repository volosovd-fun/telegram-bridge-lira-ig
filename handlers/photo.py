"""Photo handler — Gemini 2.5 Flash multimodal.

Reference: Lira-IG `app/vision.py` on VPS.
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

PROMPT_PHOTO = """Опиши це зображення українською. ≤200 слів.
Якщо це скриншот соцмережі/новини/посту — витягни ключові фрази/цифри/імена.
Якщо це фото — опиши зміст, людей, дії, текст у кадрі.
Без преамбули, одразу опис.
"""


def describe(image_bytes: bytes, mime: str = "image/jpeg") -> dict:
    """Describe image via Gemini 2.5 Flash.

    Returns:
        {"description": str} on success
        {"error": str} on failure
    """
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured"}

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": [{
            "parts": [
                {"text": PROMPT_PHOTO},
                {"inline_data": {"mime_type": mime, "data": b64}},
            ]
        }]
    }

    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
            timeout=60,
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
        return {"description": text}
    except requests.HTTPError as e:
        log.error(f"[vision] HTTP {e.response.status_code}: {e.response.text[:200]}")
        return {"error": f"HTTP {e.response.status_code}"}
    except requests.RequestException as e:
        log.error(f"[vision] request failed: {e}")
        return {"error": str(e)}


def format_photo_prefix(description: str) -> str:
    return f"[фото]: {description}"
