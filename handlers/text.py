"""Text message handler — wraps user message with role-prefix and recent_context."""

import re
import logging

log = logging.getLogger(__name__)

# Strip embedded role-prefix injection attempts
ROLE_PREFIX_PATTERN = re.compile(r"\[(Денис|Користувач|Невідомий)\]:\s*", re.IGNORECASE)


def sanitize_content(text: str) -> str:
    """Strip any '[Name]:' substrings from user content to prevent role-prefix injection."""
    return ROLE_PREFIX_PATTERN.sub("", text)


def build_message(role: str, text: str, msg_type: str, recent_context: str = "") -> str:
    """Wrap user message in structured payload for brains.

    Output:
        <recent_context>...</recent_context>

        <current_message from="Денис" type="text">
        ...sanitized text...
        </current_message>
    """
    safe_text = sanitize_content(text)
    parts = []
    if recent_context:
        parts.append(recent_context)
        parts.append("")  # blank line
    parts.append(f'<current_message from="{role}" type="{msg_type}">')
    parts.append(safe_text)
    parts.append("</current_message>")
    return "\n".join(parts)
