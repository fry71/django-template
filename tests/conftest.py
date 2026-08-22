# tests/conftest.py
from __future__ import annotations

import os
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.config.settings")
os.environ.setdefault("TASKIQ_IN_MEMORY", "true")
# Tests must be hermetic: no persistent redis cacheops state and no
# accumulated throttle counters between runs (see cache.py).
os.environ.setdefault("USE_REDIS_FOR_CACHE", "false")

import django

django.setup()

import pytest
from django.contrib.auth import get_user_model
from django.test import AsyncClient

User = get_user_model()


@pytest.fixture
def user_data() -> dict[str, str]:
    """Build unique data for creating a user."""
    unique_id = uuid.uuid4().hex[:8]
    return {
        "username": f"testuser_{unique_id}",
        "email": f"test_{unique_id}@example.com",
        "password": "testpass123",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def user_data2() -> dict[str, str]:
    """Second user data (conflicts and permission tests)."""
    unique_id = uuid.uuid4().hex[:8]
    return {
        "username": f"testuser2_{unique_id}",
        "email": f"test2_{unique_id}@example.com",
        "password": "testpass123",
        "first_name": "Second",
        "last_name": "User",
    }


@pytest.fixture
def test_user(user_data) -> User:
    """Create a test user."""
    user = User.objects.create_user(**user_data)
    yield user
    user.delete()


@pytest.fixture
def async_client() -> AsyncClient:
    """Async client for API tests."""
    return AsyncClient()


@pytest.fixture(autouse=True)
def mock_taskiq_tasks(monkeypatch) -> None:
    """Tasks are queued but not executed.

    Wrap kiq of each registered task with a stub so service tests can
    assert enqueue without running the task.
    """
    from tasks.broker import broker

    calls: list[tuple[str, tuple[object, ...]]] = []

    async def fake_kiq(self: object, *args: object, **kwargs: object) -> object:
        calls.append((getattr(self, "task_name", "<unknown>"), args))
        return None

    for task in broker.get_all_tasks().values():
        monkeypatch.setattr(task, "kiq", fake_kiq.__get__(task, type(task)))

    return calls


@pytest.fixture(autouse=True)
def _clear_throttle_cache() -> None:
    """Reset throttle counters so rate limits don't leak between tests."""
    yield
    from django.core.cache import cache

    cache.clear()
