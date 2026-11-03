# api/user/services/message_service.py
from __future__ import annotations

import logging
from types import MappingProxyType
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from django.db import transaction

from api.user.models import ChatRoom, Message
from api.user.services.cmds import (
    CreateMessageCmd,
    DeleteMessageCmd,
    GetMessageCmd,
    ListMessagesQuery,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.db.models import QuerySet

logger = logging.getLogger(__name__)

# Ordering is restricted to a whitelist: arbitrary fields are rejected.
_SORT_ORDER: Mapping[str, str] = MappingProxyType({"asc": "id", "desc": "-id"})
_DEFAULT_ORDER = "-id"


def message_queryset(query: ListMessagesQuery | None = None) -> QuerySet[Message]:
    """Return base message queryset with select_related to avoid N+1.

    Returns a lazy QuerySet — the API layer decides how to serialize it.
    """
    criteria = query or ListMessagesQuery()
    order_by = _SORT_ORDER.get(criteria.sort or "", _DEFAULT_ORDER)

    qs: QuerySet[Message] = Message.objects.select_related("sender").order_by(order_by)
    if criteria.room_id is not None:
        qs = qs.filter(room_id=criteria.room_id)
    if criteria.search:
        qs = qs.filter(content__icontains=criteria.search)
    return qs


async def create_message(cmd: CreateMessageCmd) -> Message:
    """Create a message and bump the room timestamp.

    Multi-step write (message + room touch) — atomic bridge.
    """
    return await _create_message_and_touch_room(
        sender_id=cmd.sender_id,
        room_id=cmd.room_id,
        content=cmd.content,
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


async def get_message(cmd: GetMessageCmd) -> Message | None:
    """Return message by id or None."""
    try:
        return await Message.objects.select_related("sender").aget(id=cmd.message_id)
    except Message.DoesNotExist:
        return None


async def delete_message(cmd: DeleteMessageCmd) -> bool:
    """Delete a message. Returns True/False."""
    message = await get_message(GetMessageCmd(message_id=cmd.message_id))
    if message is None:
        return False

    await message.adelete()
    logger.info("Message deleted: %s", cmd.message_id)
    return True
