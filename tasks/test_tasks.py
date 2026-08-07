# tasks/test_tasks.py
from __future__ import annotations

from tasks.broker import broker


@broker.task
async def simple_test_task(x: int, y: int) -> int:
    """Simple test task to verify Taskiq works."""
    return x + y


@broker.task
async def echo_test_task(message: str) -> str:
    """Test task that echoes messages."""
    return f"Echo: {message}"


@broker.task
async def mockable_test_task(value: str) -> str:
    """Test task that is easy to mock."""
    # Simple logic with no external dependencies
    return f"Processed: {value}"
