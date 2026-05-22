"""Telegram Bot API helpers — send / edit / reactions / chat actions.

Long-polling pattern (NOT webhook).
"""

import os
import logging
import requests
from typing import Optional

log = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
TG_FILE_API = f"https://api.telegram.org/file/bot{BOT_TOKEN}"

MAX_MSG_CHARS = 4000


def _split(text: str, limit: int = MAX_MSG_CHARS) -> list[str]:
    """Split text into chunks ≤limit chars at word boundaries."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while len(text) > limit:
        cut = text.rfind(" ", 0, limit)
        if cut == -1 or cut < limit // 2:
            cut = limit
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        chunks.append(text)
    return chunks


def send_message(chat_id: int, text: str, reply_to_message_id: Optional[int] = None,
                 parse_mode: Optional[str] = "Markdown") -> Optional[dict]:
    """Send (chunked) message. Returns first message dict or None on error."""
    chunks = _split(text)
    first_msg = None
    for i, chunk in enumerate(chunks):
        params = {
            "chat_id": chat_id,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            params["parse_mode"] = parse_mode
        if reply_to_message_id and i == 0:
            params["reply_to_message_id"] = reply_to_message_id

        try:
            resp = requests.post(f"{TG_API}/sendMessage", json=params, timeout=10)
            if resp.status_code == 400 and parse_mode:
                # Markdown parse error — fallback to plain
                log.warning(f"[tg_send] markdown failed → fallback plain: {resp.text[:200]}")
                params.pop("parse_mode", None)
                resp = requests.post(f"{TG_API}/sendMessage", json=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if i == 0:
                first_msg = data.get("result")
        except requests.RequestException as e:
            log.error(f"[tg_send] sendMessage failed: {e}")
            return None
    return first_msg


def edit_message(chat_id: int, message_id: int, text: str,
                 parse_mode: Optional[str] = "Markdown") -> bool:
    """Edit existing message. Telegram limits 4096 chars per edit."""
    text = text[:MAX_MSG_CHARS]  # truncate (chunked sends would lose original message_id)
    params = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        params["parse_mode"] = parse_mode
    try:
        resp = requests.post(f"{TG_API}/editMessageText", json=params, timeout=10)
        if resp.status_code == 400 and parse_mode:
            log.warning(f"[tg_send] editMarkdown failed → plain")
            params.pop("parse_mode", None)
            resp = requests.post(f"{TG_API}/editMessageText", json=params, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        log.error(f"[tg_send] editMessage failed: {e}")
        return False


def set_reaction(chat_id: int, message_id: int, emoji: str = "🤓") -> bool:
    """Set quick emoji reaction on user message — instant 'received' signal."""
    try:
        resp = requests.post(f"{TG_API}/setMessageReaction", json={
            "chat_id": chat_id,
            "message_id": message_id,
            "reaction": [{"type": "emoji", "emoji": emoji}],
        }, timeout=5)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        log.warning(f"[tg_send] setReaction failed (non-blocking): {e}")
        return False


def send_chat_action(chat_id: int, action: str = "typing") -> bool:
    """Send typing/upload_photo/etc indicator. Lasts ~5s."""
    try:
        requests.post(f"{TG_API}/sendChatAction", json={
            "chat_id": chat_id,
            "action": action,
        }, timeout=5)
        return True
    except requests.RequestException:
        return False


def get_file(file_id: str) -> Optional[bytes]:
    """Download file by Telegram file_id. Returns bytes or None on error."""
    try:
        # 1. Get file_path
        resp = requests.get(f"{TG_API}/getFile", params={"file_id": file_id}, timeout=10)
        resp.raise_for_status()
        file_path = resp.json()["result"]["file_path"]

        # 2. Download
        url = f"{TG_FILE_API}/{file_path}"
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return resp.content
    except requests.RequestException as e:
        log.error(f"[tg_send] getFile failed for {file_id}: {e}")
        return None


def get_me() -> dict:
    """Cache bot identity at startup."""
    resp = requests.get(f"{TG_API}/getMe", timeout=10)
    resp.raise_for_status()
    return resp.json()["result"]
