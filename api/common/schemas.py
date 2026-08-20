# api/common/schemas.py
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


def _field(description: str, **kwargs: Any) -> Any:
    """Field with metadata via pydantic v2 json_schema_extra."""
    kwargs["json_schema_extra"] = {"metadata": {"description": description}}
    return Field(**kwargs)


class OperationResultSchema(BaseModel):
    """Generic operation result (e.g. delete)."""

    detail: str = _field("Operation result message")
    status: Literal["success"] = "success"
