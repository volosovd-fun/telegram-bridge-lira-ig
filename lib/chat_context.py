"""Per-chat rolling context buffer.

Stores last N messages per chat_id (Privacy OFF → бот бачить ВСЕ в групі).
Used to give brains 'recent_context' preamble when @mention/reply triggers.
"""

import os
import time
from collections import deque
from threading import Lock
from typing import Optional

CONTEXT_SIZE = int(os.environ.get("CONTEXT_SIZE", "30"))


class ChatContextStore:
    """In-memory deque per chat_id. Lost on container restart (acceptable for V1)."""

    def __init__(self, maxlen: int = CONTEXT_SIZE):
        self.maxlen = maxlen
        self._store: dict[int, deque] = {}
        self._lock = Lock()

    def add(self, chat_id: int, role: str, text: str, msg_type: str = "text", ts: Optional[int] = None):
        """Append message to chat history."""
        ts = ts or int(time.time())
        with self._lock:
            if chat_id not in self._store:
                self._store[chat_id] = deque(maxlen=self.maxlen)
            self._store[chat_id].append({
                "role": role,
                "text": text,
                "type": msg_type,
                "ts": ts,
            })

    def recent(self, chat_id: int, limit: int = 10) -> list[dict]:
        """Return last `limit` messages from chat. Empty list if no history."""
        with self._lock:
            d = self._store.get(chat_id)
            if not d:
                return []
            return list(d)[-limit:]

    def format_preamble(self, chat_id: int, limit: int = 10) -> str:
        """Format recent context as XML preamble for brains.

        Output:
            <recent_context>
            [HH:MM Денис]: ...
            [HH:MM Користувач]: ...
            </recent_context>

        If no history — returns empty string.
        """
        msgs = self.recent(chat_id, limit)
        if not msgs:
            return ""
        lines = ["<recent_context>"]
        for m in msgs:
            t = time.strftime("%H:%M", time.localtime(m["ts"]))
            # type-specific suffix
            if m["type"] == "voice":
                preview = f"[голосове]: {m['text'][:200]}"
            elif m["type"] == "photo":
                preview = f"[фото]: {m['text'][:200]}"
            elif m["type"] == "video":
                preview = f"[відео]: {m['text'][:200]}"
            elif m["type"] == "video_note":
                preview = f"[кружечок]: {m['text'][:200]}"
            elif m["type"] == "document":
                preview = f"[файл]: {m['text'][:200]}"
            else:
                preview = m["text"][:300]
            lines.append(f"[{t} {m['role']}]: {preview}")
        lines.append("</recent_context>")
        return "\n".join(lines)


# Singleton
context_store = ChatContextStore()
