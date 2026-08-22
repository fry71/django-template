from __future__ import annotations

import logging
import sys
from os import getenv
from typing import Any

from django.core.cache import cache
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# Tests must be hermetic: no persistent cacheops state across truncated
# transactions and no throttle counters leaked between test runs.
_UNDER_PYTEST = "pytest" in sys.modules
USE_REDIS_FOR_CACHE = (
    getenv("USE_REDIS_FOR_CACHE", default="true").lower() == "true" and not _UNDER_PYTEST
)
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

    # Opt-in caching per model (cacheops recommendation: do NOT use "*.*":
    # "all" — it caches every queryset including admin, sessions, migrations,
    # and amplifies invalidation storms). Enable selectively:
    CACHEOPS = {
        "user.user": {"ops": ("fetch", "get"), "timeout": 60 * 15},
        "user.chatroom": {"ops": ("fetch", "get"), "timeout": 60 * 10},
        "user.message": {"ops": ("get",), "timeout": 60 * 5},
        # Never cache Django's internal migration recorder: it is not an
        # installed app label, so unpickling its cached rows raises LookupError.
        "migrations.*": None,
    }

    CACHEOPS_DEGRADE_ON_FAILURE = True

    try:
        from cacheops import cache as cacheops

        cacheops.set("ping", "pong")
        cacheops.get("ping")
        cacheops.delete("ping")
        logger.info("Cacheops is working properly")
    except ValueError, RedisError:
        logger.exception("Cacheops is not working. ")

    # Ping the cache to see if it's working
    try:
        cache.set("ping", "pong")

        if cache.get("ping") != "pong":
            msg = "Cache is not working properly."
            raise ValueError(msg)

        cache.delete("ping")
        logger.info("Cache is working properly")
    except ValueError, RedisError:
        logger.exception("Cache is not working. Using dummy cache instead")
        CACHES["default"] = {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
else:
    logger.warning("Using dummy cache")
    CACHES["default"] = {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
