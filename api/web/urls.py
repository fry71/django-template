from __future__ import annotations

import logging

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from api.web.routing import websocket_urlpatterns, api
from api.config.silk import USE_SILK
from api.config.storage import (
    USE_S3_FOR_MEDIA,
    USE_S3_FOR_STATIC,
)
from api.web.routing import api

logger = logging.getLogger(__name__)

urlpatterns = [
    path("", lambda _request: redirect("api/docs#/"), name="home"),
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    *websocket_urlpatterns,
]

if USE_SILK:
    urlpatterns.append(path("silk/", include("silk.urls")))

if not USE_S3_FOR_STATIC:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if not USE_S3_FOR_MEDIA:
    logger.warning("S3 is disabled, serving media files locally. Consider using S3.")
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
