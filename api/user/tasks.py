# api/user/tasks.py
from __future__ import annotations

import logging

from api.user.models import User
from tasks.broker import broker
from tasks.common import retry_with_backoff

logger = logging.getLogger(__name__)


async def _send_welcome_email(email: str) -> None:
    """Internal email-send implementation (external call)."""
    logger.info("Sending welcome email to %s", email)
    # TODO: wire up a real SMTP/email backend


@broker.task
async def send_welcome_email(user_id: int) -> None:
    """Send a welcome email to a new user.

    kiq is called from the service layer AFTER the write commits.
    """
    user = await User.objects.aget(id=user_id)
    await retry_with_backoff(
        _send_welcome_email,
        max_retries=3,
        base_delay=1.0,
        email=user.email,
    )
