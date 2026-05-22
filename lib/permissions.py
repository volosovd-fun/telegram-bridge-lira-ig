"""Permission gates for telegram-bridge-lira-ig.

Closed-by-default: unknown user_ids → silent drop after one greeting.
"""

import os
import logging

log = logging.getLogger(__name__)


def _parse_csv_ids(env_var: str) -> set[int]:
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return set()
    out = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            log.warning(f"[permissions] non-int in {env_var}: {part!r}")
    return out


# Loaded at startup
_GROUP_RAW = os.environ.get("ALLOWED_GROUP_USER_IDS", "").strip()
GROUP_OPEN = _GROUP_RAW.lower() in ("all", "*", "open")

ALLOWED_DM_USER_IDS = _parse_csv_ids("ALLOWED_DM_USER_IDS")
ALLOWED_GROUP_USER_IDS = set() if GROUP_OPEN else _parse_csv_ids("ALLOWED_GROUP_USER_IDS")
ADMIN_USER_IDS = _parse_csv_ids("ADMIN_USER_IDS")

# Sanity asserts at startup
def assert_config():
    """Fail-fast if no allowed users configured."""
    if not ALLOWED_DM_USER_IDS and not ALLOWED_GROUP_USER_IDS and not GROUP_OPEN:
        raise RuntimeError(
            "[permissions] No allowed users configured. "
            "Set ALLOWED_DM_USER_IDS and/or ALLOWED_GROUP_USER_IDS in env."
        )
    group_desc = "OPEN (all members)" if GROUP_OPEN else f"{len(ALLOWED_GROUP_USER_IDS)} users"
    log.info(
        f"[permissions] DM whitelist: {len(ALLOWED_DM_USER_IDS)} users; "
        f"Group whitelist: {group_desc}; "
        f"Admins: {len(ADMIN_USER_IDS)}"
    )


def is_dm_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_DM_USER_IDS


def is_group_allowed(user_id: int) -> bool:
    if GROUP_OPEN:
        return True
    return user_id in ALLOWED_GROUP_USER_IDS


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS


def role_label(user_id: int) -> str:
    """Return short role label for logs and role-prefix injection."""
    if user_id == 245649:
        return "Денис"
    if GROUP_OPEN or user_id in ALLOWED_GROUP_USER_IDS:
        return "Користувач"
    return "Невідомий"
