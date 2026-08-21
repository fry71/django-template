# api/user/services/room_service.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from django.db import IntegrityError, transaction

from api.common.exceptions import ConflictError, PermissionDeniedError
from api.user.models import ChatRoom, RoomMembership, RoomType, direct_room_key

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from api.user.schema import RoomCreateIn

logger = logging.getLogger(__name__)


def room_queryset() -> QuerySet[ChatRoom]:
    """Return base room queryset with prefetch to avoid N+1."""
    return ChatRoom.objects.prefetch_related("members").select_related("created_by")


async def get_room(room_id: int) -> ChatRoom | None:
    """Return room by id or None."""
    try:
        return await room_queryset().aget(id=room_id)
    except ChatRoom.DoesNotExist:
        return None


async def create_room(user_id: int, payload: RoomCreateIn) -> ChatRoom:
    """Create a group room and add the creator as its first member.

    Multi-step write (room + membership) — atomic bridge.
    """
    try:
        return await _create_room_with_member(
            name=payload.name,
            is_private=payload.is_private,
            creator_id=user_id,
        )
    except IntegrityError as exc:
        msg = "Room creation conflict"
        raise ConflictError(msg) from exc


@sync_to_async
@transaction.atomic
def _create_room_with_member(
    *,
    name: str,
    is_private: bool,
    creator_id: int,
) -> ChatRoom:
    room = ChatRoom.objects.create(
        name=name,
        room_type=RoomType.GROUP,
        is_private=is_private,
        created_by_id=creator_id,
    )
    RoomMembership.objects.create(room=room, user_id=creator_id)
    logger.info("Room created: %s by user %s", room.id, creator_id)
    return room


async def get_or_create_direct_room(user_a_id: int, user_b_id: int) -> ChatRoom:
    """Return the existing 1:1 room between two users or create it.

    Multi-step write (room + two memberships) — atomic bridge.
    """
    key = direct_room_key(user_a_id, user_b_id)
    existing = await room_queryset().filter(direct_key=key).afirst()
    if existing is not None:
        return existing
    return await _create_direct_room(key=key, user_a_id=user_a_id, user_b_id=user_b_id)


@sync_to_async
@transaction.atomic
def _create_direct_room(key: str, user_a_id: int, user_b_id: int) -> ChatRoom:
    room = ChatRoom.objects.create(
        name=key,
        room_type=RoomType.DIRECT,
        is_private=True,
        direct_key=key,
        created_by_id=user_a_id,
    )
    RoomMembership.objects.bulk_create(
        [
            RoomMembership(room=room, user_id=user_a_id),
            RoomMembership(room=room, user_id=user_b_id),
        ],
    )
    logger.info("Direct room created: %s", room.id)
    return room


async def join_room(room_id: int, user_id: int) -> bool:
    """Add a user to a public room. Returns False if the room is missing."""
    room = await get_room(room_id)
    if room is None:
        return False
    if room.is_private:
        msg = "Cannot join a private room"
        raise PermissionDeniedError(msg)
    await RoomMembership.objects.aget_or_create(room_id=room.id, user_id=user_id)
    logger.info("User %s joined room %s", user_id, room.id)
    return True


async def leave_room(room_id: int, user_id: int) -> bool:
    """Remove a user from a room. Returns False if the room is missing."""
    exists = await ChatRoom.objects.filter(id=room_id).aexists()
    if not exists:
        return False
    deleted, _ = await RoomMembership.objects.filter(
        room_id=room_id,
        user_id=user_id,
    ).adelete()
    return deleted > 0


async def is_member(room_id: int, user_id: int) -> bool:
    """Return whether the user belongs to the room."""
    return await RoomMembership.objects.filter(
        room_id=room_id,
        user_id=user_id,
    ).aexists()
