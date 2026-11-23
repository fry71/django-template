# api/common/controllers.py
from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, TypeVar

from dmr import Controller, ResponseSpec
from dmr.errors import ErrorDetail, ErrorModel, format_error
from dmr.headers import HeaderSpec
from dmr.pagination.cursor import InvalidCursorError
from dmr.plugins.pydantic import PydanticFastSerializer
from dmr.serializer import BaseSerializer

from api.common.exceptions import DomainError, RateLimitError

if TYPE_CHECKING:
    from django.http import HttpResponse
    from dmr.endpoint import Endpoint

# Every 401 needs a challenge (RFC 9110, section 15.5.2) and every 429 needs
# retry information, so both are part of the declared contract and enforced by
# response validation: dmr adds the challenge and the throttling headers for
# its own auth and throttling, and ``_error_headers`` adds the rate-limit
# headers of domain errors.
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
            # Integer headers per the dmr 0.17 `HeaderSpec.type` convention.
            "Retry-After": HeaderSpec(
                description="Seconds to wait before retrying",
                type=int,
                example=60,
            ),
            "X-RateLimit-Limit": HeaderSpec(
                description="Requests allowed per window",
                type=int,
                example=10,
            ),
            "X-RateLimit-Remaining": HeaderSpec(
                description="Requests left in the window",
                type=int,
                example=0,
            ),
            "X-RateLimit-Reset": HeaderSpec(
                description="Seconds until the window resets",
                type=int,
                example=60,
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
    """Mixin mapping domain and dmr cursor errors to structured responses."""

    async def handle_async_error(
        self,
        endpoint: Endpoint,  # DMR passes it by contract
        controller: Controller[BaseSerializer],
        exc: Exception,
    ) -> HttpResponse:
        """Convert a DomainError or InvalidCursorError into a response.

        ``InvalidCursorError`` is deliberately not handled by dmr's own
        global handler: a cursor is a client-provided value, so a
        malformed one is this API's ``400``. The status is already
        declared by ``ERROR_RESPONSES``.
        """
        if isinstance(exc, InvalidCursorError):
            return self.to_error(  # type: ignore[attr-defined]
                format_error(str(exc), error_type="invalid_cursor"),
                status_code=HTTPStatus.BAD_REQUEST,
            )
        if not isinstance(exc, DomainError):
            raise exc
        return self.to_error(  # type: ignore[attr-defined]
            _domain_error_model(exc),
            status_code=HTTPStatus(exc.status_code),
            headers=_error_headers(exc),
        )


_SerializerT = TypeVar(
    "_SerializerT",
    bound=BaseSerializer,
    default=PydanticFastSerializer,
)


class BaseAsyncController(DomainErrorMixin, Controller[_SerializerT]):
    """Async controller mapping domain errors to structured responses.

    JSON-only endpoints keep the ``PydanticFastSerializer`` default
    (about x2.2 faster deserialize). A controller with non-JSON parsers
    passes its own serializer, like ``BaseAsyncController[PydanticSerializer]``
    for multipart uploads: the fast serializer only supports
    ``application/json`` and raises ``EndpointMetadataError`` otherwise.
    """

    responses = ERROR_RESPONSES
