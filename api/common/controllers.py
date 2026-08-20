# api/common/controllers.py
from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from dmr import Controller, ResponseSpec
from dmr.errors import ErrorModel, format_error
from dmr.plugins.pydantic import PydanticSerializer

from api.common.exceptions import DomainError

if TYPE_CHECKING:
    from django.http import HttpResponse
    from dmr.endpoint import Endpoint

_ERROR_RESPONSES = (
    ResponseSpec(ErrorModel, status_code=HTTPStatus.BAD_REQUEST),
    ResponseSpec(ErrorModel, status_code=HTTPStatus.UNAUTHORIZED),
    ResponseSpec(ErrorModel, status_code=HTTPStatus.FORBIDDEN),
    ResponseSpec(ErrorModel, status_code=HTTPStatus.NOT_FOUND),
    ResponseSpec(ErrorModel, status_code=HTTPStatus.CONFLICT),
)


class BaseAsyncController(Controller[PydanticSerializer]):
    """Async controller mapping domain errors to structured responses."""

    responses = _ERROR_RESPONSES

    async def handle_async_error(
        self,
        endpoint: Endpoint,  # noqa: ARG002 - DMR passes it by contract
        controller: Controller[PydanticSerializer],  # noqa: ARG002
        exc: Exception,
    ) -> HttpResponse:
        """Convert a DomainError into an ErrorModel response."""
        if isinstance(exc, DomainError):
            return self.to_error(
                format_error(
                    exc.detail,
                    loc=["body"],
                    error_type=exc.code,
                ),
                status_code=HTTPStatus(exc.status_code),
            )
        raise exc
