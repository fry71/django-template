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

# Headers are documented for clients but not enforced on domain errors:
# dmr adds ``WWW-Authenticate`` when its own auth rejects a request, and the
# throttle adds the rate-limit headers on 429, while a domain error of the same
# status carries neither (``skip_validation`` keeps response validation happy).
ERROR_RESPONSES = (
    ResponseSpec(ErrorModel, status_code=HTTPStatus.BAD_REQUEST),
    ResponseSpec(
        ErrorModel,
        status_code=HTTPStatus.UNAUTHORIZED,
        headers={
            "WWW-Authenticate": HeaderSpec(
                description="Auth scheme that rejected the request",
                skip_validation=True,
            ),
        },
    ),
    ResponseSpec(ErrorModel, status_code=HTTPStatus.FORBIDDEN),
    ResponseSpec(ErrorModel, status_code=HTTPStatus.NOT_FOUND),
    ResponseSpec(ErrorModel, status_code=HTTPStatus.CONFLICT),
    ResponseSpec(
        ErrorModel,
        status_code=HTTPStatus.TOO_MANY_REQUESTS,
        headers={
            "Retry-After": HeaderSpec(
                description="Seconds to wait before retrying",
                skip_validation=True,
            ),
            "X-RateLimit-Limit": HeaderSpec(
                description="Requests allowed per window",
                skip_validation=True,
            ),
            "X-RateLimit-Remaining": HeaderSpec(
                description="Requests left in the window",
                skip_validation=True,
            ),
            "X-RateLimit-Reset": HeaderSpec(
                description="Seconds until the window resets",
                skip_validation=True,
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


def _rate_limit_headers(exc: DomainError) -> dict[str, str] | None:
    """Return rate-limit headers for a lockout response."""
    if not isinstance(exc, RateLimitError):
        return None
    retry_after = str(exc.retry_after)
    return {
        "Retry-After": retry_after,
        "X-RateLimit-Limit": str(exc.limit),
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": retry_after,
    }


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
            headers=_rate_limit_headers(exc),
        )


class BaseAsyncController(DomainErrorMixin, Controller[PydanticSerializer]):
    """Async controller mapping domain errors to structured responses."""

    responses = ERROR_RESPONSES
