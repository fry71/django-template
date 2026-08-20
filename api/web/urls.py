from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.urls import include, path
from dmr.openapi.views import OpenAPIJsonView, SwaggerView

from api.config.silk import USE_SILK
from api.config.storage import USE_S3_FOR_STATIC
from api.user import views
from api.web.routing import (
    router,
    schema,
    websocket_urlpatterns,
)
from api.web.views import health

urlpatterns = [
    path("", lambda _request: redirect("api/docs#/"), name="home"),
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    router.to_urlpatterns(namespace="api"),
    path("api/docs/", SwaggerView.as_view(schema), name="api-docs"),
    path("api/openapi.json", OpenAPIJsonView.as_view(schema), name="api-openapi"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("chat/", views.chat_view, name="chat"),
    path("chat/send/", views.send_message, name="chat-send"),
    path("chat/stream/", views.message_stream, name="chat-stream"),
    *websocket_urlpatterns,
]

if USE_SILK:
    urlpatterns.append(path("silk/", include("silk.urls")))

if not USE_S3_FOR_STATIC:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
