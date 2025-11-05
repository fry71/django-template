# tasks/broker.py
import os
import django
from django.conf import settings
from taskiq_redis import RedisAsyncResultBackend, ListQueueBroker
from taskiq import InMemoryBroker
import logging

logger = logging.getLogger(__name__)


def create_broker():
    """Create Taskiq broker."""
    logger.info("Creating Taskiq broker")

    # Инициализация Django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.config.settings")
    try:
        django.setup()
    except Exception as e:
        logger.error(f"Failed to initialize Django: {e}")
        raise

    # Для разработки используем InMemoryBroker
    # if settings.DEBUG:
    #     logger.info("Using InMemoryBroker for development")
    #     return InMemoryBroker()

    # Для production используем Redis
    redis_config = getattr(settings, "TASKIQ_REDIS", {})
    redis_url = redis_config.get("URL", "redis://localhost:6379/3")

    if not redis_url:
        logger.error("TASKIQ_REDIS.URL is not configured")
        raise ValueError("TASKIQ_REDIS.URL is not configured")

    try:
        broker = ListQueueBroker(
            redis_url,
            queue_name="taskiq",
        ).with_result_backend(RedisAsyncResultBackend(redis_url))
        logger.info("Redis broker created successfully")
        return broker
    except Exception as e:
        logger.error(f"Failed to create Redis broker: {e}")
        raise


# Создание брокера
broker = create_broker()
