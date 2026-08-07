# tests/unit/test_tasks.py
from __future__ import annotations

import pytest

from api.user.schema import UserCreateIn
from api.user.services import user_service
from api.user.tasks import send_welcome_email


@pytest.mark.django_db(transaction=True)
class TestTaskDispatch:
    async def test_create_user_enqueues_welcome_email(
        self,
        user_data: dict[str, str],
        mock_taskiq_tasks,
    ) -> None:
        payload = UserCreateIn(**user_data)
        await user_service.create_user(payload)

        queued = [name for name, _args in mock_taskiq_tasks]
        assert send_welcome_email.task_name in queued

    async def test_task_is_queued_not_executed(
        self,
        mock_taskiq_tasks,
    ) -> None:
        await send_welcome_email.kiq(42)
        assert any(name == send_welcome_email.task_name for name, _ in mock_taskiq_tasks)


@pytest.mark.django_db(transaction=True)
class TestRetryWithBackoff:
    async def test_retry_on_transient_error(self) -> None:
        from tasks.common import retry_with_backoff

        attempts: list[int] = []

        async def flaky(*, ok_after: int = 2) -> str:
            attempts.append(1)
            if len(attempts) < ok_after:
                msg = "transient"
                raise OSError(msg)
            return "done"

        result = await retry_with_backoff(flaky, max_retries=3, base_delay=0)
        assert result == "done"
        assert len(attempts) == 2
