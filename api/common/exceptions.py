# api/common/exceptions.py
from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base domain exception.

    The API layer catches this and maps it to an HTTP response.
    The service layer never returns HTTP statuses — only domain errors.
    """

    status_code: int = 400
    code: str | None = None

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
    code: str = "not_found"


class ConflictError(DomainError):
    """Conflict with current resource state (e.g. duplicate)."""

    status_code: int = 409
    code: str = "conflict"


class ValidationError(DomainError):
    """Business-rule validation error."""

    status_code: int = 400
    code: str = "validation_error"


class PermissionDeniedError(DomainError):
    """Insufficient permissions for the operation."""

    status_code: int = 403
    code: str = "permission_denied"


class UnauthorizedError(DomainError):
    """User is not authenticated."""

    status_code: int = 401
    code: str = "unauthorized"


type ErrorContext = dict[str, Any] | None
