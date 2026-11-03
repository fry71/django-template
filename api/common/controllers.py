# api/common/controllers.py
from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from dmr import Controller, ResponseSpec
from dmr.errors import ErrorDetail, ErrorModel, format_error
from dmr.headers import HeaderSpec
from dmr.plugins.pydantic import PydanticSerializer

from api.common.exceptions import DomainError, RateLimitError

if TYPE_CHECKING:
    from django.http import HttpResponse
    from dmr.endpoint import Endpoint

# Every 401 needs a challenge (RFC 9110, section 15.5.2) and every 429 needs
# retry information, so both are part of the declared contract and enforced by
# response validation: dmr adds them for its own auth and throttling, and
# ``_error_headers`` adds them for domain errors.
AUTHENTICATION_REQUIRED = ResponseSpec(
    ErrorModel,
    status_code=HTTPStatus.UNAUTHORIZED,
    headers={
        "WWW-Authenticate": HeaderSpec(
            description="Auth scheme that rejected the request",
            example="Bearer",
        ),
    },
)

ERROR_RESPONSES = (
    ResponseSpec(ErrorModel, status_code=HTTPStatus.BAD_REQUEST),
    AUTHENTICATION_REQUIRED,
    ResponseSpec(ErrorModel, status_code=HTTPStatus.FORBIDDEN),
    ResponseSpec(ErrorModel, status_code=HTTPStatus.NOT_FOUND),
    ResponseSpec(ErrorModel, status_code=HTTPStatus.CONFLICT),
    ResponseSpec(
        ErrorModel,
        status_code=HTTPStatus.TOO_MANY_REQUESTS,
        headers={
            "Retry-After": HeaderSpec(
                description="Seconds to wait before retrying",
            ),
            "X-RateLimit-Limit": HeaderSpec(
                description="Requests allowed per window",
            ),
            "X-RateLimit-Remaining": HeaderSpec(
                description="Requests left in the window",
            ),
            "X-RateLimit-Reset": HeaderSpec(
                description="Seconds until the window resets",
            ),
        },
    ),
)


def _domain_error_model(exc: DomainError) -> ErrorModel:
    """Build an ErrorModel for a domain error.

    Field-level errors are positioned exactly like DMR positions its own
    validation errors (``["parsed_body", field]``), so clients can handle
    transport and domain validation with the same code.
    """
    if not exc.fields:
        return format_error(exc.detail, error_type=exc.code)

    detail: list[ErrorDetail] = []
    for field_name, messages in exc.fields.items():
        for message in messages:
            field_error = format_error(
                message,
                loc=["parsed_body", field_name],
                error_type=exc.code,
            )
            detail.extend(field_error["detail"])
    return {"detail": detail}


def _error_headers(exc: DomainError) -> dict[str, str] | None:
    """Return the protocol headers that must accompany a domain error."""
    if isinstance(exc, RateLimitError):
        retry_after = str(exc.retry_after)
        return {
            "Retry-After": retry_after,
            "X-RateLimit-Limit": str(exc.limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": retry_after,
        }
    return None


class DomainErrorMixin:
    """Mixin mapping domain errors to structured responses."""

    async def handle_async_error(
        self,
        endpoint: Endpoint,  # DMR passes it by contract
        controller: Controller[PydanticSerializer],
        exc: Exception,
    ) -> HttpResponse:
        """Convert a DomainError into an ErrorModel response."""
        if not isinstance(exc, DomainError):
            raise exc
        return self.to_error(  # type: ignore[attr-defined]
            _domain_error_model(exc),
            status_code=HTTPStatus(exc.status_code),
            headers=_error_headers(exc),
        )


class BaseAsyncController(DomainErrorMixin, Controller[PydanticSerializer]):
    """Async controller mapping domain errors to structured responses."""

    responses = ERROR_RESPONSES
