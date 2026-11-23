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


@pytest.fixture(scope="session")
def tracecov_map():  # type: ignore[no-any-return]
    """Session TraceCov map; ``None`` keeps the default run untracked.

    Opt-in contract coverage — which OpenAPI operations and parameters
    the tests actually exercised:

        TRACECOV=1 uv run pytest tests

    The dmr pytest plugin wires every ``dmr_client``/``dmr_async_client``
    request into this map automatically. Caveat: the tracecov Django
    client wrapper reads ``request.body``, which Django forbids for
    multipart once the stream is parsed, so a tracked run must skip
    the upload tests (``-k "not TestPhotoApi"``) until tracecov fixes it.
    """
    if not os.environ.get("TRACECOV"):
        return None
    try:
        import tracecov
    except ImportError:  # pragma: no cover
        return None

    from api.web.routing import schema

    return tracecov.CoverageMap.from_dict(schema.convert())
