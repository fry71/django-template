# api/common/schemas.py
from __future__ import annotations

from typing import Any, Literal

from ninja import Schema
from pydantic import Field


def _field(description: str, **kwargs: Any) -> Any:
    """Field with metadata via pydantic v2 json_schema_extra."""
    kwargs["json_schema_extra"] = {"metadata": {"description": description}}
    return Field(**kwargs)


class ErrorSchema(Schema):
    """Structured error response shared across the project."""

    detail: str = _field("Human-readable error description")
    code: str | None = _field(
        "Machine-readable error code for client logic",
        default=None,
    )
    fields: dict[str, list[str]] | None = _field(
        "Per-field validation errors",
        default=None,
    )


class OperationResultSchema(Schema):
    """Generic operation result (e.g. delete)."""

    detail: str = _field("Operation result message")
    status: Literal["success"] = "success"


type ErrorPayload = dict[str, Any]
