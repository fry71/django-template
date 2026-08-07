# tasks/__init__.py
from __future__ import annotations

import logging
import os
from importlib import import_module

import django
from django.apps import apps

from .broker import broker

logger = logging.getLogger(__name__)

__all__ = ["broker"]


def register_tasks() -> None:
    """Register tasks from all Django apps (tasks.py in each app)."""
    for app_config in apps.get_app_configs():
        try:
            import_module(f"{app_config.name}.tasks")
        except ImportError:
            continue

    import_module("tasks.test_tasks")


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.config.settings")

try:
    django.setup()
    register_tasks()
    logger.info("Registered %d tasks", len(broker.get_all_tasks()))
except Exception:
    logger.exception("Failed to initialize tasks")
