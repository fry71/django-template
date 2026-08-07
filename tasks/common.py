# tasks/common.py
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from tasks.broker import broker

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


def get_broker() -> Any:
    """DI provider for the Taskiq broker (TaskiqDepends)."""
    return broker


async def retry_with_backoff(
    func: Callable[..., Any],
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    **kwargs: Any,
) -> Any:
    """Run a function with exponential backoff for transient errors.

    Permanent errors are re-raised immediately; transient ones retry 3 times.
    """
    for attempt in range(max_retries):
        try:
            return await func(**kwargs)
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2**attempt)
            logger.warning(
                "Transient error (attempt %d/%d): %s. Retrying in %.1fs",
                attempt + 1,
                max_retries,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
    msg = "Unreachable"
    raise RuntimeError(msg)  # pragma: no cover
