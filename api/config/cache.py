from __future__ import annotations

import logging
from os import getenv
from typing import Any


from django.core.cache import cache
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

USE_REDIS_FOR_CACHE = getenv("USE_REDIS_FOR_CACHE", default="true").lower() == "true"
REDIS_URL = getenv("REDIS_URL", default="redis://redis:6379/0")
# REDIS_PASSWORD = getenv("REDIS_PASSWORD", default="guest")
logger.info("USE_REDIS_FOR_CACHE: %s", USE_REDIS_FOR_CACHE)
CACHES: dict[str, Any] = {}

if USE_REDIS_FOR_CACHE:
    logger.info("Using Redis for cache")
    CACHES["default"] = {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
    CACHEOPS_REDIS = REDIS_URL[:-1] + "1"

    CACHEOPS_DEFAULTS = {"timeout": 60 * 60}

    CACHEOPS = {
        # "api.user.*": {"ops": "all", "timeout": 60 * 15},
        # "auth.permission": {"ops": "all", "timeout": 60 * 60},
        # "auth.*": {"ops": ("fetch", "get"), "timeout": 60 * 60},
        "*.*": {"ops": "all", "timeout": 60 * 15},
    }

    CACHEOPS_DEGRADE_ON_FAILURE = True

    try:
        from cacheops import cache as cacheops

        cacheops.set("ping", "pong")
        cacheops.get("ping")
        cacheops.delete("ping")
        logger.info("Cacheops is working properly")
    except (ValueError, RedisError):
        logger.exception("Cacheops is not working. ")

    # Ping the cache to see if it's working
    try:
        cache.set("ping", "pong")

        if cache.get("ping") != "pong":
            msg = "Cache is not working properly."
            raise ValueError(msg)  # noqa: TRY301

        cache.delete("ping")
        logger.info("Cache is working properly")
    except (ValueError, RedisError):
        logger.exception("Cache is not working. Using dummy cache instead")
        CACHES["default"] = {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
else:
    logger.warning("Using dummy cache")
    CACHES["default"] = {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
