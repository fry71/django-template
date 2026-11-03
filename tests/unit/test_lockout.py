# tests/unit/test_lockout.py
from __future__ import annotations

from api.common import lockout


async def test_lockout_after_max_failures() -> None:
    username = "someone"

    for _ in range(lockout.MAX_FAILED_LOGINS - 1):
        await lockout.register_failure(username)
    assert not await lockout.is_locked(username)

    await lockout.register_failure(username)
    assert await lockout.is_locked(username)


async def test_successful_login_resets_failures() -> None:
    username = "someone"
    for _ in range(lockout.MAX_FAILED_LOGINS):
        await lockout.register_failure(username)
    assert await lockout.is_locked(username)

    await lockout.reset(username)

    assert not await lockout.is_locked(username)


async def test_lockout_is_per_username() -> None:
    for _ in range(lockout.MAX_FAILED_LOGINS):
        await lockout.register_failure("victim")

    assert await lockout.is_locked("victim")
    assert not await lockout.is_locked("bystander")


async def test_username_is_not_stored_in_clear_text() -> None:
    key = lockout._counter_key("Alice")

    assert "alice" not in key.lower()
    assert key == lockout._counter_key(" alice ")
