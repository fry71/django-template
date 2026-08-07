# api/web/routing.py
from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import re_path
from ninja import NinjaAPI

from api.common.exceptions import DomainError
from api.common.schemas import ErrorSchema
from api.user import consumers
from api.user.api import router as user_router

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<token>[^/]+)/$", consumers.ChatConsumer.as_asgi()),
]

api = NinjaAPI(
    title="Django Gateway API",
    version="0.1.0",
    description="High performance Django API with async capabilities",
    docs_url="/docs",
    openapi_url="/openapi.json",
)


@api.exception_handler(DomainError)
def handle_domain_error(request: HttpRequest, exc: DomainError) -> HttpResponse:
    """Global handler for service-layer domain errors."""
    return api.create_response(
        request,
        ErrorSchema(detail=exc.detail, code=exc.code, fields=exc.fields),
        status=exc.status_code,
    )


api.add_router("/user/", user_router, tags=["user"])
