"""PDF document handler — Gemini 2.5 Flash multimodal PDF input.

Telegram getFile limit 20MB.
Other doc types (docx, txt, zip) — reject in V1.
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

MAX_PDF_BYTES = 20 * 1024 * 1024

PROMPT_PDF = """Витягни ключові факти з PDF українською. ≤500 слів.
Структура:
1. Тема документу (1 речення)
2. Найважливіші 5-7 фактів/тверджень
3. Цифри, дати, імена (якщо є)
4. Висновки чи рекомендації (якщо є)

Без преамбули, одразу витяжка.
"""


def extract(pdf_bytes: bytes, filename: str = "document.pdf") -> dict:
    """Extract key facts from PDF via Gemini multimodal.

    Returns:
        {"summary": str, "filename": str} on success
        {"error": str} on failure
    """
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured"}

    if len(pdf_bytes) > MAX_PDF_BYTES:
        return {"error": "PDF too large (>20MB Telegram Bot API limit)"}

    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    payload = {
        "contents": [{
            "parts": [
                {"text": PROMPT_PDF},
                {"inline_data": {"mime_type": "application/pdf", "data": b64}},
            ]
        }]
    }

    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
            timeout=180,
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
        return {"summary": text, "filename": filename}
    except requests.HTTPError as e:
        log.error(f"[pdf] HTTP {e.response.status_code}: {e.response.text[:200]}")
        return {"error": f"HTTP {e.response.status_code}"}
    except requests.RequestException as e:
        log.error(f"[pdf] request failed: {e}")
        return {"error": str(e)}


def format_pdf_prefix(summary: str, filename: str) -> str:
    return f"[файл PDF: {filename}]: {summary}"
