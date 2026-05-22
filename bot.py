#!/usr/bin/env python3
"""telegram-bridge-lira-ig — long-polling Telegram adapter (TEST channel for Ліра).

Calls lira-ig-v2 via Trinity REST /api/agents/{name}/chat.
Multimodal preprocessing: voice (ElevenLabs), photo/video/video_note/PDF (Gemini).

NOT a webhook. Long-polling pattern (no public URL needed).
Paralel до IG webhook; session_id=tg:{chat_id} ізольований від ig:{sender_id}.
"""

import os
import re
import sys
import time
import logging
import threading
import requests
from pathlib import Path

# Load .env BEFORE lib imports (lib modules read env at module-level)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # dotenv may not be installed yet on first boot — Trinity exports env directly

# Ensure WORKSPACE-relative imports work
sys.path.insert(0, str(Path(__file__).parent))

from lib import permissions
from lib.chat_context import context_store
from lib.trinity_client import chat_with_agent
from lib.tg_send import (
    send_message, edit_message, set_reaction, send_chat_action,
    get_file, get_me, TG_API,
)
from handlers import text as h_text
from handlers import voice as h_voice
from handlers import photo as h_photo
from handlers import video as h_video
from handlers import document as h_doc
from handlers import command as h_command


# Logging
LOG_DIR = Path(os.environ.get("WORKSPACE", "/home/developer")) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "bot.log"),
    ],
)
log = logging.getLogger("lira-ig-bridge")


# Globals (set at startup)
BOT_ID: int = 0
BOT_USERNAME: str = ""

# Marker pattern for cross-bot questions to Lira (or others).
# Brains writes: [ASK_LIRA: @Lira_assist_ai_bot ...question...]
# Bridge strips marker from user-visible response and sends a separate message to chat.
ASK_LIRA_PATTERN = re.compile(r"\[ASK_LIRA:\s*(.+?)\]", re.DOTALL | re.IGNORECASE)


def extract_and_strip_ask_lira(response: str) -> tuple[str, list[str]]:
    """Find [ASK_LIRA: ...] markers in response.

    Returns (clean_response_for_user, [list_of_lira_questions]).
    """
    questions = ASK_LIRA_PATTERN.findall(response)
    clean = ASK_LIRA_PATTERN.sub("", response).strip()
    return clean, [q.strip() for q in questions]


def is_for_bot(message: dict) -> bool:
    """Check if message is for the bot: @mention | reply | DM | command.

    With Privacy OFF, bot sees ALL group messages → must filter to direct addressing.
    """
    chat_type = message.get("chat", {}).get("type", "")
    if chat_type == "private":
        return True

    # Group: check entities for mention
    text = message.get("text", "") or message.get("caption", "")
    entities = message.get("entities", []) or message.get("caption_entities", [])
    for ent in entities:
        if ent.get("type") == "mention":
            offset = ent["offset"]
            length = ent["length"]
            mentioned = text[offset:offset + length]
            if mentioned.lower() == f"@{BOT_USERNAME.lower()}":
                return True
        if ent.get("type") == "text_mention":
            user = ent.get("user", {})
            if user.get("id") == BOT_ID:
                return True

    # Reply to bot
    reply = message.get("reply_to_message", {})
    if reply.get("from", {}).get("id") == BOT_ID:
        return True

    # /commands
    for ent in entities:
        if ent.get("type") == "bot_command":
            return True

    return False


def keep_typing(chat_id: int, stop_event: threading.Event):
    """Background loop to refresh typing/upload action while brains processes."""
    while not stop_event.is_set():
        send_chat_action(chat_id, "typing")
        stop_event.wait(4.5)


def process_message(update: dict):
    """Main per-update handler."""
    message = update.get("message")
    if not message:
        return  # ignore edited_message, callback_query, etc for V1

    chat = message.get("chat", {})
    chat_id = chat["id"]
    chat_type = chat.get("type", "private")
    from_user = message.get("from", {})
    user_id = from_user.get("id", 0)
    text = message.get("text", "") or message.get("caption", "") or ""
    msg_id = message.get("message_id")

    # 1) Permissions gate
    if chat_type == "private":
        if not permissions.is_dm_allowed(user_id):
            log.info(f"[security] silent drop DM from user_id={user_id}")
            return  # silent drop — DM тільки для Дениса, нікому іншому не відповідаємо
    else:
        if not permissions.is_group_allowed(user_id):
            log.info(f"[security] silent drop group msg from user_id={user_id}")
            return

    role = permissions.role_label(user_id)

    # 2) Always store in chat_context (even if not for-bot — for context buffer)
    msg_type = "text"
    text_for_context = text
    if message.get("voice"):
        msg_type = "voice"
        text_for_context = "[voice note]"
    elif message.get("photo"):
        msg_type = "photo"
        text_for_context = text or "[photo]"
    elif message.get("video"):
        msg_type = "video"
        text_for_context = text or "[video]"
    elif message.get("video_note"):
        msg_type = "video_note"
        text_for_context = "[video note]"
    elif message.get("document"):
        msg_type = "document"
        text_for_context = text or f"[{message['document'].get('file_name', 'document')}]"

    context_store.add(chat_id, role, text_for_context, msg_type, ts=message.get("date"))

    # 3) Filter — only proceed if message is FOR bot
    if not is_for_bot(message):
        log.debug(f"[filter] message in chat {chat_id} not for bot — stored only")
        return

    log.info(f"[handler] from={role}({user_id}) chat={chat_id} type={msg_type}")

    # 4) Quick acknowledgment 🤓
    set_reaction(chat_id, msg_id, "🤓")

    # 5) Send placeholder — different per type
    placeholder_text = {
        "text": "💭 думаю...",
        "voice": "🎙 слухаю...",
        "photo": "📷 дивлюсь...",
        "video": "🎬 аналізую відео...",
        "video_note": "🎬 дивлюсь кружечок...",
        "document": "📄 читаю файл...",
    }.get(msg_type, "💭 ...")

    placeholder = send_message(chat_id, placeholder_text, reply_to_message_id=msg_id, parse_mode=None)
    if not placeholder:
        log.error("[handler] could not send placeholder, aborting")
        return
    placeholder_id = placeholder["message_id"]

    # 6) Typing keepalive (only useful in DM — Telegram suppresses for bots in groups)
    stop_typing = threading.Event()
    if chat_type == "private":
        threading.Thread(target=keep_typing, args=(chat_id, stop_typing), daemon=True).start()

    try:
        # 7) Multimodal preprocessing — convert media to text prefix
        msg_text = ""
        if msg_type == "voice":
            voice_obj = message["voice"]
            audio_bytes = get_file(voice_obj["file_id"])
            if not audio_bytes:
                edit_message(chat_id, placeholder_id, "⚠ не зміг завантажити голосове", parse_mode=None)
                return
            duration = voice_obj.get("duration", 0)
            if duration > 600:  # 10 min hard cap V1
                edit_message(chat_id, placeholder_id,
                             f"⚠ голосове задовге ({duration}s). V1 максимум 10 хв.", parse_mode=None)
                return
            result = h_voice.transcribe(audio_bytes)
            if "error" in result:
                edit_message(chat_id, placeholder_id, f"⚠ STT помилка: {result['error']}", parse_mode=None)
                return
            msg_text = h_voice.format_voice_prefix(result["transcript"], result["duration"])
            edit_message(chat_id, placeholder_id, f"🎙 {result['transcript'][:200]}\nоброблюю...",
                         parse_mode=None)

        elif msg_type == "photo":
            photo_arr = message["photo"]
            largest = max(photo_arr, key=lambda p: p.get("file_size", 0))
            img_bytes = get_file(largest["file_id"])
            if not img_bytes:
                edit_message(chat_id, placeholder_id, "⚠ не зміг завантажити фото", parse_mode=None)
                return
            result = h_photo.describe(img_bytes)
            if "error" in result:
                edit_message(chat_id, placeholder_id, f"⚠ vision помилка: {result['error']}", parse_mode=None)
                return
            msg_text = h_photo.format_photo_prefix(result["description"])

        elif msg_type == "video":
            video_obj = message["video"]
            file_size = video_obj.get("file_size", 0)
            if file_size > 20 * 1024 * 1024:
                edit_message(chat_id, placeholder_id,
                             "⚠ відео >20MB. Telegram Bot API limit. Скинь коротше.",
                             parse_mode=None)
                return
            video_bytes = get_file(video_obj["file_id"])
            if not video_bytes:
                edit_message(chat_id, placeholder_id, "⚠ не зміг завантажити відео", parse_mode=None)
                return
            duration = video_obj.get("duration", 0)
            result = h_video.analyze(video_bytes, mime=video_obj.get("mime_type", "video/mp4"),
                                     duration_seconds=duration)
            if "error" in result:
                edit_message(chat_id, placeholder_id, f"⚠ video analysis: {result['error']}", parse_mode=None)
                return
            msg_text = h_video.format_video_prefix(result["description"], result["duration"])

        elif msg_type == "video_note":
            vn_obj = message["video_note"]
            video_bytes = get_file(vn_obj["file_id"])
            if not video_bytes:
                edit_message(chat_id, placeholder_id, "⚠ не зміг завантажити кружечок", parse_mode=None)
                return
            duration = vn_obj.get("duration", 0)
            result = h_video.analyze(video_bytes, mime="video/mp4", duration_seconds=duration)
            if "error" in result:
                edit_message(chat_id, placeholder_id, f"⚠ video_note: {result['error']}", parse_mode=None)
                return
            msg_text = h_video.format_video_prefix(result["description"], duration, is_video_note=True)

        elif msg_type == "document":
            doc_obj = message["document"]
            mime = doc_obj.get("mime_type", "")
            filename = doc_obj.get("file_name", "document")
            if mime != "application/pdf":
                edit_message(chat_id, placeholder_id,
                             f"⚠ V1 підтримую тільки PDF. Цей: {mime or 'unknown'}",
                             parse_mode=None)
                return
            file_size = doc_obj.get("file_size", 0)
            if file_size > 20 * 1024 * 1024:
                edit_message(chat_id, placeholder_id, "⚠ PDF >20MB. Скинь меншу версію.",
                             parse_mode=None)
                return
            pdf_bytes = get_file(doc_obj["file_id"])
            if not pdf_bytes:
                edit_message(chat_id, placeholder_id, "⚠ не зміг завантажити PDF", parse_mode=None)
                return
            result = h_doc.extract(pdf_bytes, filename)
            if "error" in result:
                edit_message(chat_id, placeholder_id, f"⚠ PDF: {result['error']}", parse_mode=None)
                return
            msg_text = h_doc.format_pdf_prefix(result["summary"], filename)

        else:
            # text — check for command
            cmd = h_command.detect(text)
            if cmd:
                # Permission check for admin-only commands
                if cmd["admin_only"] and not permissions.is_admin(user_id):
                    edit_message(chat_id, placeholder_id,
                                 "⚠ ця команда тільки для Дениса", parse_mode=None)
                    return
                # Build structured command payload
                payload_str = h_command.build_command_payload(
                    cmd["command"], cmd["content"], role, user_id
                )
                msg_text = f"<command>\n{payload_str}\n</command>"
                msg_msg_type = "command"
            else:
                msg_text = text
                msg_msg_type = "text"

            # Build full payload with recent_context
            preamble = context_store.format_preamble(chat_id, limit=10)
            full_payload = h_text.build_message(role, msg_text, msg_msg_type, preamble)

            response, _ = chat_with_agent(full_payload, session_id=f"tg:{chat_id}")
            clean_response, lira_questions = extract_and_strip_ask_lira(response)
            edit_message(chat_id, placeholder_id, clean_response or "...", parse_mode="Markdown")
            for q in lira_questions[:1]:  # cap at 1 per turn
                log.info(f"[ask_lira] forwarding to Ліра: {q[:120]}...")
                send_message(chat_id, q, parse_mode=None)
            return

        # Multimodal path (voice/photo/video/video_note/document) — common tail
        preamble = context_store.format_preamble(chat_id, limit=10)
        full_payload = h_text.build_message(role, msg_text, msg_type, preamble)
        response, _ = chat_with_agent(full_payload, session_id=f"tg:{chat_id}")
        clean_response, lira_questions = extract_and_strip_ask_lira(response)
        edit_message(chat_id, placeholder_id, clean_response or "...", parse_mode="Markdown")
        for q in lira_questions[:1]:
            log.info(f"[ask_lira] forwarding to Ліра: {q[:120]}...")
            send_message(chat_id, q, parse_mode=None)

    except requests.Timeout:
        edit_message(chat_id, placeholder_id, "⚠ запит затягнувся (>180s). Спробуй ще раз.",
                     parse_mode=None)
    except Exception as e:
        log.exception("[handler] unhandled error")
        edit_message(chat_id, placeholder_id, f"⚠ помилка: {type(e).__name__}", parse_mode=None)
    finally:
        stop_typing.set()


def long_poll_loop():
    """Main polling loop."""
    offset = 0
    log.info(f"[main] starting long-poll loop, offset={offset}")
    while True:
        try:
            resp = requests.get(
                f"{TG_API}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                log.error(f"[main] getUpdates not ok: {data}")
                time.sleep(5)
                continue
            updates = data.get("result", [])
            for upd in updates:
                offset = max(offset, upd["update_id"] + 1)
                try:
                    process_message(upd)
                except Exception:
                    log.exception("[main] error processing update")
        except requests.RequestException as e:
            log.warning(f"[main] poll error: {e}")
            time.sleep(5)


def main():
    global BOT_ID, BOT_USERNAME

    # Validate config
    permissions.assert_config()

    # Get bot identity
    me = get_me()
    BOT_ID = me["id"]
    BOT_USERNAME = me["username"]
    log.info(f"[main] Bot @{BOT_USERNAME} (id={BOT_ID}) is ready!")
    log.info(f"[main] DM whitelist: {len(permissions.ALLOWED_DM_USER_IDS)} users")
    log.info(f"[main] Group whitelist: {len(permissions.ALLOWED_GROUP_USER_IDS)} users")

    # Polling
    long_poll_loop()


if __name__ == "__main__":
    main()
