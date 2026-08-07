from __future__ import annotations

import json
import logging.config
from os import getenv

LOG_LEVEL = getenv("LOG_LEVEL", default="INFO")
LOG_FORMAT = getenv("LOG_FORMAT", default="colored")  # colored | json


class JsonFormatter(logging.Formatter):
    """Structured JSON formatter for logs (per AGENTS.md 1.4)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if getattr(record, "extra", None):
            payload["extra"] = record.extra
        return json.dumps(payload, ensure_ascii=False, default=str)


def _build_config() -> dict[str, object]:
    if LOG_FORMAT == "json":
        formatters: dict[str, object] = {
            "json": {
                "()": "api.config.logging.JsonFormatter",
            },
        }
        handlers: dict[str, object] = {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            },
        }
    else:
        formatters = {
            "colored": {
                "()": "colorlog.ColoredFormatter",
                "format": "%(asctime)s %(log_color)s%(levelname)s %(name)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        }
        handlers = {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "colored",
            },
        }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "loggers": {
            "": {
                "handlers": ["console"],
                "level": LOG_LEVEL,
                "propagate": True,
            },
        },
    }


LOGGING = _build_config()

logging.config.dictConfig(LOGGING)
