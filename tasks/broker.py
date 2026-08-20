# tasks/broker.py
from __future__ import annotations

import logging
import os
from contextlib import suppress
from importlib import import_module

import django
from django.apps import apps
from django.conf import settings
from taskiq import InMemoryBroker
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

logger = logging.getLogger(__name__)


def register_tasks() -> None:
    """Import taskiq tasks so they register with the broker.

    Imports each Django app's ``tasks.py`` plus the local test-task module.
    """
    for app_config in apps.get_app_configs():
        with suppress(ImportError):
            import_module(f"{app_config.name}.tasks")

    import_module("tasks.test_tasks")


def create_broker() -> InMemoryBroker | ListQueueBroker:
    """Create a Taskiq broker.

    In tests/dev with TASKIQ_IN_MEMORY=true, InMemoryBroker is used so
    tasks are queued but not executed.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.config.settings")
    try:
        django.setup()
    except Exception:
        logger.exception("Failed to initialize Django")
        raise

    if getattr(settings, "TASKIQ_IN_MEMORY", False):
        logger.info("Using InMemoryBroker")
        return InMemoryBroker()

    redis_url = getattr(settings, "TASKIQ_REDIS", {}).get(
        "URL",
        "redis://localhost:6379/3",
    )
    if not redis_url:
        msg = "TASKIQ_REDIS.URL is not configured"
        logger.error(msg)
        raise ValueError(msg)

    try:
        broker = ListQueueBroker(
            redis_url,
            queue_name="taskiq",
        ).with_result_backend(RedisAsyncResultBackend(redis_url))
    except Exception:
        logger.exception("Failed to create Redis broker")
        raise
    logger.info("Redis broker created successfully")
    return broker


broker = create_broker()
register_tasks()
logger.info("Registered %d tasks", len(broker.get_all_tasks()))
