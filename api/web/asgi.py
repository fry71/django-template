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

from api.web import routing  # noqa: E402 - app modules load after Django setup


def _is_media_request(scope: dict[str, Any]) -> bool:
    """Check whether the scope is an HTTP media request."""
    return scope["type"] == "http" and scope["path"].startswith(settings.MEDIA_URL)


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


async def serve_media(scope: dict[str, Any], receive: Any, send: Any) -> None:
    """Async function to serve media files."""
    if not _is_media_request(scope):
        return await django_application(scope, receive, send)

    file_path = scope["path"].replace(settings.MEDIA_URL, "", 1)
    full_path = Path(settings.MEDIA_ROOT) / file_path

    if not full_path.exists() or not full_path.is_file():
        await _send_response(send, 404, "text/plain", b"File not found")
        return None

    content_type = mimetypes.guess_type(full_path)[0] or "application/octet-stream"

    try:
        async with aiofiles.open(full_path, "rb") as media_file:
            file_bytes = await media_file.read()
    except OSError:
        await _send_response(send, 500, "text/plain", b"Internal server error")
        return None

    await _send_response(
        send,
        200,
        content_type,
        file_bytes,
    )
    return None


application = ProtocolTypeRouter(
    {
        "http": URLRouter(
            [
                path("media/<path:path>", serve_media),
                re_path(r"", django_application),
            ],
        ),
        "websocket": AuthMiddlewareStack(URLRouter(routing.websocket_urlpatterns)),
    },
)
