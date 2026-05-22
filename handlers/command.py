"""Command handler — parse @додай-style commands and forward as structured payload to brains."""

import re
import json
import time
import logging

log = logging.getLogger(__name__)


# Regexes for @Контентщик commands
COMMAND_PATTERNS = [
    (re.compile(r"^@\w+\s+додай\s+факт:\s*(.+)$", re.IGNORECASE | re.DOTALL), "add_fact", False),
    (re.compile(r"^@\w+\s+додай\s+історію:\s*(.+)$", re.IGNORECASE | re.DOTALL), "add_story", False),
    (re.compile(r"^@\w+\s+додай\s+в\s+voice\s+file:\s*(.+)$", re.IGNORECASE | re.DOTALL), "add_to_voice_file", True),
    (re.compile(r"^@\w+\s+заборони\s+слово:\s*(.+)$", re.IGNORECASE), "ban_word", True),
    (re.compile(r"^@\w+\s+не\s+знімай\s+про\s+(.+)$", re.IGNORECASE), "dont_film", True),
    (re.compile(r"^@\w+\s+undo\s*$", re.IGNORECASE), "undo", False),
    (re.compile(r"^@\w+\s+покажи\s+свою\s+базу\s*$", re.IGNORECASE), "show_kb", False),
    (re.compile(r"^@\w+\s+історія\s+знань\s*$", re.IGNORECASE), "show_history", False),
]


def detect(text: str) -> dict | None:
    """Detect if text is a @Контентщик command.

    Returns:
        {"command": "...", "content": "...", "admin_only": bool}
        or None if not a command.
    """
    for pattern, command, admin_only in COMMAND_PATTERNS:
        m = pattern.match(text.strip())
        if m:
            content = m.group(1).strip() if m.groups() else ""
            return {
                "command": command,
                "content": content,
                "admin_only": admin_only,
            }
    return None


def build_command_payload(command: str, content: str, role: str, user_id: int) -> str:
    """Build structured payload for brains. Sent as `current_message type=command`."""
    payload = {
        "command": command,
        "from": role,
        "from_user_id": user_id,
        "content": content,
        "ts": int(time.time()),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
