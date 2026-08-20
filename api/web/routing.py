# api/web/routing.py
from __future__ import annotations

from django.urls import re_path
from dmr.openapi import build_schema
from dmr.openapi.config import OpenAPIConfig
from dmr.routing import Router, path

from api.user import consumers
from api.user.api import (
    MeController,
    MessageDetailController,
    MessageListController,
    ObtainAccessAndRefreshController,
    PhotoListController,
    RefreshAccessAndRefreshController,
    UserDetailController,
    UserListController,
)

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<token>[^/]+)/$", consumers.ChatConsumer.as_asgi()),
]

router = Router(
    "api/",
    [
        path("user/token", ObtainAccessAndRefreshController.as_view(), name="token"),
        path(
            "user/refresh",
            RefreshAccessAndRefreshController.as_view(),
            name="refresh",
        ),
        path("user/me", MeController.as_view(), name="me"),
        path("user/users", UserListController.as_view(), name="user-list"),
        path(
            "user/users/<int:user_id>",
            UserDetailController.as_view(),
            name="user-detail",
        ),
        path("user/messages", MessageListController.as_view(), name="message-list"),
        path(
            "user/messages/<int:message_id>",
            MessageDetailController.as_view(),
            name="message-detail",
        ),
        path("user/photos", PhotoListController.as_view(), name="photo-list"),
    ],
)

schema = build_schema(
    router,
    config=OpenAPIConfig(
        title="Django Gateway API",
        version="0.1.0",
        description="High performance Django API with async capabilities",
    ),
)
