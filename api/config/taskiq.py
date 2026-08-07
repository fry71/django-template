from __future__ import annotations

import logging
from os import getenv

logger = logging.getLogger(__name__)

TASKIQ_IN_MEMORY = getenv("TASKIQ_IN_MEMORY", default="false").lower() == "true"
TASKIQ_REDIS = {
    "URL": getenv(
        "TASKIQ_REDIS_URL",
        default="redis://localhost:6379/3",
    ),
}

if TASKIQ_IN_MEMORY:
    logger.info("Taskiq runs in-memory (tasks are queued but not executed)")
else:
    logger.info("Taskiq uses Redis broker: %s", TASKIQ_REDIS["URL"])
