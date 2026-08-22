# api/web/urls.py
from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from dmr.openapi.views import OpenAPIJsonView, SwaggerView

from api.config.silk import USE_SILK
from api.config.storage import USE_S3_FOR_STATIC
from api.web.routing import router, schema
from api.web.views import health

urlpatterns = [
    path("", lambda _request: redirect("api/docs#/"), name="home"),
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    router.to_urlpatterns(namespace="api"),
    path("api/docs/", SwaggerView.as_view(schema), name="api-docs"),
    path("api/openapi.json", OpenAPIJsonView.as_view(schema), name="api-openapi"),
]

if USE_SILK:
    urlpatterns.append(path("silk/", include("silk.urls")))

if not USE_S3_FOR_STATIC:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
