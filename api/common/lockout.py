# api/common/lockout.py
"""Failed-login lockout backed by the cache (Redis in production).

This is the async replacement for a database-backed lockout handler: the
counter lives in the cache, every operation is a cache round-trip, and the
login hot path never touches the ORM. Usernames are hashed before they become
cache keys, so raw identifiers never end up in Redis.

A cache outage must not block logins, so every failure falls back to
"not locked" (fail-open) and is logged.
"""

from __future__ import annotations

import logging
from hashlib import sha256
from os import getenv

from django.core.cache import cache

logger = logging.getLogger(__name__)

MAX_FAILED_LOGINS = int(getenv("LOGIN_MAX_FAILED_ATTEMPTS", default="5"))
LOCKOUT_SECONDS = int(getenv("LOGIN_LOCKOUT_SECONDS", default="900"))


def _counter_key(username: str) -> str:
    """Return the cache key for a username without storing it in clear text."""
    digest = sha256(username.strip().lower().encode("utf-8")).hexdigest()
    return f"login-failures::{digest}"


async def is_locked(username: str) -> bool:
    """Return whether the account is currently locked out."""
    return await _read_failures(username) >= MAX_FAILED_LOGINS


async def register_failure(username: str) -> int:
    """Count one failed login and (re)start the lockout window.

    Returns the number of failures counted so far; ``0`` means the counter
    could not be updated.
    """
    try:
        failures = await _count_failure(_counter_key(username))
    except Exception:  # a cache outage must not block logins
        logger.exception("Failed to record a failed login for %s", username)
        return 0
    return int(failures or 0)


async def reset(username: str) -> None:
    """Forget previous failures after a successful login."""
    try:
        await cache.adelete(_counter_key(username))
    except Exception:  # a cache outage must not block logins
        logger.exception("Failed to reset failed logins for %s", username)


async def _read_failures(username: str) -> int:
    try:
        failures = await cache.aget(_counter_key(username), 0)
    except Exception:  # a cache outage must not block logins
        logger.exception("Failed to read failed logins for %s", username)
        return 0
    return int(failures or 0)


async def _count_failure(key: str) -> int:
    """Create the counter with a TTL or bump the existing one."""
    added = await cache.aadd(key, 1, timeout=LOCKOUT_SECONDS)
    if added:
        return 1
    return int(await cache.aincr(key) or 0)
