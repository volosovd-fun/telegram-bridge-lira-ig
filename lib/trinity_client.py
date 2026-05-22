"""Trinity REST API client — POST /api/agents/{name}/chat.

180s timeout (vs 60s for Public Chat API), no max_turns=10 limit.
"""

import os
import logging
import requests
from typing import Optional

log = logging.getLogger(__name__)

TRINITY_API_URL = os.environ.get("TRINITY_API_URL", "http://trinity-backend:8000")
TRINITY_MCP_API_KEY = os.environ.get("TRINITY_MCP_API_KEY")  # Trinity injects automatically
TARGET_AGENT = os.environ.get("TARGET_AGENT", "lira-ig-v2")
SOURCE_AGENT = "telegram-bridge-lira-ig"
TIMEOUT_SECONDS = 180


def chat_with_agent(message: str, session_id: Optional[str] = None) -> tuple[str, Optional[str]]:
    """Call lira-ig-v2 via REST /api/agents/{name}/chat.

    Returns (response_text, session_id).
    """
    if not TRINITY_MCP_API_KEY:
        raise RuntimeError("TRINITY_MCP_API_KEY missing — Trinity should auto-inject this")

    url = f"{TRINITY_API_URL}/api/agents/{TARGET_AGENT}/chat"
    headers = {
        "Authorization": f"Bearer {TRINITY_MCP_API_KEY}",
        "Content-Type": "application/json",
        "X-Source-Agent": SOURCE_AGENT,
    }
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    log.info(f"[trinity] POST chat session={session_id} msg_len={len(message)}")

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.Timeout:
        log.error(f"[trinity] timeout after {TIMEOUT_SECONDS}s")
        raise
    except requests.HTTPError as e:
        log.error(f"[trinity] HTTP {resp.status_code}: {resp.text[:200]}")
        raise

    data = resp.json()
    response_text = data.get("response", "...")
    new_session_id = data.get("session", {}).get("session_id") or session_id
    log.info(f"[trinity] response_len={len(response_text)} session={new_session_id}")
    return response_text, new_session_id
