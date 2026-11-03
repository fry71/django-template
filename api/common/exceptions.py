# api/common/exceptions.py
from __future__ import annotations

from typing import Any, ClassVar


class DomainError(Exception):
    """Base domain exception.

    The API layer catches this and maps it to an HTTP response.
    The service layer never returns HTTP statuses — only domain errors.
    """

    status_code: int = 400
    code: ClassVar[str | None] = None

    def __init__(
        self,
        detail: str,
        *,
        fields: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.fields = fields


class NotFoundError(DomainError):
    """Resource not found."""

    status_code: int = 404
    code = "not_found"


class ConflictError(DomainError):
    """Conflict with current resource state (e.g. duplicate)."""

    status_code: int = 409
    code = "conflict"


class ValidationError(DomainError):
    """Business-rule validation error."""

    status_code: int = 400
    code = "validation_error"


class PermissionDeniedError(DomainError):
    """Insufficient permissions for the operation."""

    status_code: int = 403
    code = "permission_denied"


class UnauthorizedError(DomainError):
    """User is not authenticated."""

    status_code: int = 401
    code = "unauthorized"


class RateLimitError(DomainError):
    """Too many requests or attempts; the caller should retry later."""

    status_code: int = 429
    code = "rate_limited"


type ErrorContext = dict[str, Any] | None
