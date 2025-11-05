# tasks/test_tasks.py
from __future__ import annotations
from tasks.broker import broker
from taskiq import TaskiqDepends


@broker.task
async def simple_test_task(x: int, y: int) -> int:
    """Простая тестовая задача для проверки работы Taskiq"""
    return x + y


@broker.task
async def echo_test_task(message: str) -> str:
    """Тестовая задача для эхо-сообщений"""
    return f"Echo: {message}"


@broker.task
async def mockable_test_task(value: str) -> str:
    """Тестовая задача, которую можно легко замокать"""
    # Простая логика без внешних зависимостей
    return f"Processed: {value}"
