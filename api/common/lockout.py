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
import time
from dataclasses import dataclass
from hashlib import sha256
from os import getenv

from django.core.cache import cache

logger = logging.getLogger(__name__)

MAX_FAILED_LOGINS = int(getenv("LOGIN_MAX_FAILED_ATTEMPTS", default="5"))
LOCKOUT_SECONDS = int(getenv("LOGIN_LOCKOUT_SECONDS", default="900"))


@dataclass(frozen=True, slots=True, kw_only=True)
class LockoutState:
    """Result of a lockout check."""

    failures: int
    retry_after: int

    @property
    def locked(self) -> bool:
        """Whether the account must be refused for now."""
        return self.failures >= MAX_FAILED_LOGINS


def _digest(username: str) -> str:
    """Return a stable, non-reversible key part for a username."""
    return sha256(username.strip().lower().encode("utf-8")).hexdigest()


def _counter_key(username: str) -> str:
    return f"login-failures::{_digest(username)}"


def _since_key(username: str) -> str:
    return f"login-failures-since::{_digest(username)}"


async def check(username: str) -> LockoutState:
    """Return the current lockout state for a username."""
    failures = await _read_failures(username)
    if failures < MAX_FAILED_LOGINS:
        return LockoutState(failures=failures, retry_after=0)

    elapsed = _elapsed_seconds(await _read_since(username))
    remaining = LOCKOUT_SECONDS - elapsed
    return LockoutState(
        failures=failures,
        retry_after=remaining if remaining > 0 else LOCKOUT_SECONDS,
    )


async def is_locked(username: str) -> bool:
    """Return whether the account is currently locked out."""
    return (await check(username)).locked


async def register_failure(username: str) -> int:
    """Count one failed login and (re)start the lockout window.

    Returns the number of failures counted so far; ``0`` means the counter
    could not be updated.
    """
    try:
        failures = await _count_failure(username)
    except Exception:  # a cache outage must not block logins
        logger.exception("Failed to record a failed login for %s", username)
        return 0
    return int(failures or 0)


async def reset(username: str) -> None:
    """Forget previous failures after a successful login."""
    try:
        await cache.adelete_many(
            [_counter_key(username), _since_key(username)],
        )
    except Exception:  # a cache outage must not block logins
        logger.exception("Failed to reset failed logins for %s", username)


async def _count_failure(username: str) -> int:
    """Create the counter with a TTL or bump the existing one."""
    counter = _counter_key(username)
    if await cache.aadd(counter, 1, timeout=LOCKOUT_SECONDS):
        await _mark_started(username)
        return 1
    return int(await cache.aincr(counter) or 0)


async def _mark_started(username: str) -> None:
    """Remember when the current lockout window started."""
    await cache.aset(
        _since_key(username),
        int(time.time()),
        timeout=LOCKOUT_SECONDS,
    )


def _elapsed_seconds(started_at: int) -> int:
    """Return how long ago the lockout window started."""
    if not started_at:
        return 0
    return max(0, int(time.time()) - started_at)


async def _read_failures(username: str) -> int:
    try:
        failures = await cache.aget(_counter_key(username), 0)
    except Exception:  # a cache outage must not block logins
        logger.exception("Failed to read failed logins for %s", username)
        return 0
    return int(failures or 0)


async def _read_since(username: str) -> int:
    try:
        started_at = await cache.aget(_since_key(username), 0)
    except Exception:  # a cache outage must not block logins
        logger.exception("Failed to read the lockout window for %s", username)
        return 0
    return int(started_at or 0)
