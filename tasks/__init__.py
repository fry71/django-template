# tasks/__init__.py
import os
from importlib import import_module
from django.apps import apps
from .broker import broker
from . import common
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

__all__ = ["broker", "common"]

# Registration tasks from apps
def register_tasks():
    """Register tasks from all Django apps."""
    for app_config in apps.get_app_configs():
        try:
            tasks_module = f"{app_config.name}.tasks"
            import_module(tasks_module)
            logger.info(f"Tasks module loaded: {tasks_module}")
        except ImportError:
            continue
    
    # Загружаем тестовые задачи
    try:
        import_module("tasks.test_tasks")
        logger.info("Test tasks loaded")
    except ImportError as e:
        logger.warning(f"Could not load test tasks: {e}")

# Инициализация Django и регистрация задач
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.config.settings")

try:
    import django
    django.setup()
    register_tasks()
except Exception as e:
    logger.error(f"Failed to initialize tasks: {e}")

if settings.DEBUG:
    logger.info("Registered tasks:")
    for name in broker.get_all_tasks():
        logger.info(f"- {name}")