# api/web/asgi.py
from __future__ import annotations
import os

import aiofiles
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.conf import settings
from django.core.asgi import get_asgi_application
from django.urls import path, re_path
import mimetypes

from api.web import routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.config.settings")

# Django application
django_application = get_asgi_application()


async def serve_media(scope, receive, send):
    """Async function to serve media files"""
    if scope["type"] != "http":
        return await django_application(scope, receive, send)

    # Извлекаем путь из scope
    path = scope["path"]
    if not path.startswith(settings.MEDIA_URL):
        return await django_application(scope, receive, send)

    file_path = path.replace(settings.MEDIA_URL, "", 1)
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)

    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        await send(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": [(b"Content-Type", b"text/plain")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"File not found",
            }
        )
        return

    content_type, _ = mimetypes.guess_type(full_path)
    content_type = content_type or "application/octet-stream"

    try:
        async with aiofiles.open(full_path, "rb") as f:
            content = await f.read()
    except Exception as e:
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"Content-Type", b"text/plain")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"Internal server error",
            }
        )
        return

    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"Content-Type", content_type.encode("utf-8")),
                (b"Content-Length", str(len(content)).encode("utf-8")),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": content,
        }
    )


application = ProtocolTypeRouter(
    {
        "http": URLRouter(
            [
                path("media/<path:path>", serve_media),
                re_path(r"", django_application),
            ]
        ),
        "websocket": AuthMiddlewareStack(URLRouter(routing.websocket_urlpatterns)),
    }
)
