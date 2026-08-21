# api/user/services/message_service.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from django.db import transaction

from api.user.models import ChatRoom, Message

if TYPE_CHECKING:
    from django.db.models import QuerySet

logger = logging.getLogger(__name__)


def message_queryset(
    room_id: int | None = None,
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
    if room_id is not None:
        qs = qs.filter(room_id=room_id)
    if search:
        qs = qs.filter(content__icontains=search)
    return qs


async def create_message(
    sender_id: int,
    room_id: int,
    message_content: str,
) -> Message:
    """Create a message and bump the room timestamp.

    Multi-step write (message + room touch) — atomic bridge.
    """
    return await _create_message_and_touch_room(
        sender_id=sender_id,
        room_id=room_id,
        content=message_content,
    )


@sync_to_async
@transaction.atomic
def _create_message_and_touch_room(
    sender_id: int,
    room_id: int,
    content: str,
) -> Message:
    message = Message.objects.create(
        sender_id=sender_id,
        room_id=room_id,
        content=content,
    )
    ChatRoom.objects.filter(id=room_id).update(updated_at=message.timestamp)
    logger.info("Message created in room %s: %s", room_id, message.id)
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
