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
ALLOWED_DM_USER_IDS = _parse_csv_ids("ALLOWED_DM_USER_IDS")
ALLOWED_GROUP_USER_IDS = _parse_csv_ids("ALLOWED_GROUP_USER_IDS")
ADMIN_USER_IDS = _parse_csv_ids("ADMIN_USER_IDS")

# Sanity asserts at startup
def assert_config():
    """Fail-fast if no allowed users configured."""
    if not ALLOWED_DM_USER_IDS and not ALLOWED_GROUP_USER_IDS:
        raise RuntimeError(
            "[permissions] No allowed users configured. "
            "Set ALLOWED_DM_USER_IDS and/or ALLOWED_GROUP_USER_IDS in env."
        )
    log.info(
        f"[permissions] DM whitelist: {len(ALLOWED_DM_USER_IDS)} users; "
        f"Group whitelist: {len(ALLOWED_GROUP_USER_IDS)} users; "
        f"Admins: {len(ADMIN_USER_IDS)}"
    )


def is_dm_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_DM_USER_IDS


def is_group_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_GROUP_USER_IDS


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS


def role_label(user_id: int) -> str:
    """Return short role label for logs and role-prefix injection."""
    # NOTE: hardcoded for test — Денис=245649. Інших можна додати ручками тут
    # або через generic "Користувач".
    if user_id == 245649:
        return "Денис"
    if user_id in ALLOWED_GROUP_USER_IDS:
        return "Користувач"
    return "Невідомий"
