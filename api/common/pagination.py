# api/common/pagination.py
from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING, Any

from dmr.pagination import Page

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.db.models import Model, QuerySet


@dataclass(slots=True)
class PageInfo:
    """Count metadata for a paginated query."""

    count: int
    num_pages: int


async def paginate[TItem: Model](
    queryset: QuerySet[TItem],
    page_number: int,
    page_size: int,
) -> tuple[Sequence[TItem], PageInfo]:
    """Slice an async queryset into a page plus count metadata.

    Returns ``(records, info)`` where ``records`` is the slice for
    ``page_number`` and ``info`` carries ``count`` and ``num_pages``.
    """
    count = await queryset.acount()
    num_pages = max(1, ceil(count / page_size))
    safe_page = min(page_number, num_pages)
    offset = (safe_page - 1) * page_size
    records: Sequence[TItem] = [
        record async for record in queryset[offset : offset + page_size]
    ]
    return records, PageInfo(count=count, num_pages=num_pages)


def build_page[TPage, TItem](
    page_model: type[TPage],
    records: Sequence[TItem],
    info: PageInfo,
    page_number: int,
    page_size: int,
) -> TPage:
    """Assemble a DMR paginated response from serialized records."""
    factory: Any = page_model
    return factory(
        count=info.count,
        num_pages=info.num_pages,
        per_page=page_size,
        page=Page(
            number=min(page_number, info.num_pages),
            object_list=list(records),
        ),
    )
