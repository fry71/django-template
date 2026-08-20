# api/web/asgi.py
from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any

import aiofiles
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.conf import settings
from django.core.asgi import get_asgi_application
from django.urls import path, re_path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.config.settings")

# Django application (must be created before importing app modules)
django_application = get_asgi_application()

from api.web import routing  # app modules load after Django setup


def _is_file_request(scope: dict[str, Any], url_prefix: str) -> bool:
    """Check whether the scope is an HTTP request under a URL prefix."""
    return scope["type"] == "http" and scope["path"].startswith(url_prefix)


async def _send_response(
    send: Any,
    status: int,
    content_type: str,
    body: bytes,
) -> None:
    """Send a raw HTTP response."""
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"Content-Type", content_type.encode("utf-8"))],
        },
    )
    await send(
        {
            "type": "http.response.body",
            "body": body,
        },
    )


async def _serve_file_from_root(
    scope: dict[str, Any],
    receive: Any,
    send: Any,
    url_prefix: str,
    root: str,
) -> None:
    """Serve a file from a directory root without hitting Django."""
    if not _is_file_request(scope, url_prefix):
        await django_application(scope, receive, send)
        return

    file_path = scope["path"].replace(url_prefix, "", 1)
    full_path = Path(root) / file_path

    if not full_path.exists() or not full_path.is_file():
        await _send_response(send, 404, "text/plain", b"File not found")
        return

    content_type = mimetypes.guess_type(full_path)[0] or "application/octet-stream"

    try:
        async with aiofiles.open(full_path, "rb") as file:
            file_bytes = await file.read()
    except OSError:
        await _send_response(send, 500, "text/plain", b"Internal server error")
        return

    await _send_response(
        send,
        200,
        content_type,
        file_bytes,
    )


async def serve_media(scope: dict[str, Any], receive: Any, send: Any) -> None:
    """Serve media files without Django."""
    await _serve_file_from_root(
        scope,
        receive,
        send,
        settings.MEDIA_URL,
        settings.MEDIA_ROOT,
    )


async def serve_static(scope: dict[str, Any], receive: Any, send: Any) -> None:
    """Serve static files without Django."""
    await _serve_file_from_root(
        scope,
        receive,
        send,
        settings.STATIC_URL,
        settings.STATIC_ROOT,
    )


application = ProtocolTypeRouter(
    {
        "http": URLRouter(
            [
                path("media/<path:path>", serve_media),
                path("static/<path:path>", serve_static),
                re_path(r"", django_application),
            ],
        ),
        "websocket": AuthMiddlewareStack(URLRouter(routing.websocket_urlpatterns)),
    },
)
