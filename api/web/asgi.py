# api/web/asgi.py
from __future__ import annotations

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.config.settings")

# Django application (must be created before importing app modules)
django_application = get_asgi_application()

from api.web import routing  # app modules load after Django setup

# Static files are served by WhiteNoise middleware (or nginx / S3 in
# production). Media files are served by nginx or the S3-compatible storage.
application = ProtocolTypeRouter(
    {
        "http": django_application,
        "websocket": AuthMiddlewareStack(URLRouter(routing.websocket_urlpatterns)),
    },
)
