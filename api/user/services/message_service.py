# api/user/services/message_service.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from api.user.models import Message

if TYPE_CHECKING:
    from django.db.models import QuerySet

logger = logging.getLogger(__name__)


def message_queryset(
    search: str | None = None,
    sort: str | None = None,
) -> QuerySet[Message]:
    """Return base message queryset with select_related to avoid N+1.

    Returns a lazy QuerySet — the API layer decides how to serialize it.
    Sorting is restricted to a whitelist (arbitrary fields are rejected).
    """
    allowed_sort = {"-id", "-timestamp", "timestamp", "id"}
    order_by = sort if sort in allowed_sort else "-id"

    qs: QuerySet[Message] = Message.objects.select_related("sender").order_by(order_by)
    if search:
        qs = qs.filter(content__icontains=search)
    return qs


async def create_message(sender_id: int, message_content: str) -> Message:
    """Create a message — simple write (single INSERT)."""
    message = await Message.objects.acreate(
        sender_id=sender_id,
        content=message_content,
    )
    logger.info("Message created: %s", message.id)
    return message


async def get_message(message_id: int) -> Message | None:
    """Return message by id or None."""
    try:
        return await Message.objects.select_related("sender").aget(id=message_id)
    except Message.DoesNotExist:
        return None


async def delete_message(message_id: int) -> bool:
    """Delete a message. Returns True/False."""
    message = await get_message(message_id)
    if message is None:
        return False

    await message.adelete()
    logger.info("Message deleted: %s", message_id)
    return True
