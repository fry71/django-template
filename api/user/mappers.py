# api/user/mappers.py
"""Boundary mappers: Pydantic schema <-> service command <-> domain object.

Controllers never pass schemas into services and services never build
schemas: this module is the only place where the two worlds meet.
"""

from __future__ import annotations

from api.user import schema
from api.user.services import cmds


def create_user_cmd(payload: schema.UserCreateIn) -> cmds.CreateUserCmd:
    """Map a create-user request to the service command."""
    return cmds.CreateUserCmd(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        first_name=payload.first_name,
        last_name=payload.last_name,
        patronymic=payload.patronymic,
    )


def update_user_cmd(user_id: int, payload: schema.UserUpdateIn) -> cmds.UpdateUserCmd:
    """Map a partial update request, keeping "not provided" apart from ``None``."""
    provided = payload.model_dump(exclude_unset=True)
    return cmds.UpdateUserCmd(user_id=user_id, **provided)


def create_room_cmd(payload: schema.RoomCreateIn, creator_id: int) -> cmds.CreateRoomCmd:
    """Map a create-room request to the service command."""
    return cmds.CreateRoomCmd(
        name=payload.name,
        creator_id=creator_id,
        is_private=payload.is_private,
    )


def list_messages_query(payload: schema.MessagePageQuery) -> cmds.ListMessagesQuery:
    """Map message list filters to the service query."""
    return cmds.ListMessagesQuery(
        room_id=payload.room_id,
        search=payload.search,
        sort=payload.sort,
    )


def create_message_cmd(
    payload: schema.MessageIn,
    sender_id: int,
) -> cmds.CreateMessageCmd:
    """Map a create-message request to the service command."""
    return cmds.CreateMessageCmd(
        sender_id=sender_id,
        room_id=payload.room_id,
        content=payload.content,
    )


def user_out(user: object) -> schema.UserOutSchema:
    """Map a user domain object to its response schema."""
    return schema.UserOutSchema.model_validate(user, from_attributes=True)


def room_out(room: object) -> schema.RoomOut:
    """Map a room domain object to its response schema."""
    return schema.RoomOut.model_validate(room, from_attributes=True)


def message_out(message: object) -> schema.MessageOut:
    """Map a message domain object to its response schema."""
    return schema.MessageOut.model_validate(message, from_attributes=True)


def photo_out(photo: object) -> schema.PhotoOut:
    """Map a photo domain object to its response schema."""
    return schema.PhotoOut.model_validate(photo, from_attributes=True)
