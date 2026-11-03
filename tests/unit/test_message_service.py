# tests/unit/test_message_service.py
from __future__ import annotations

import pytest

from api.user.models import ChatRoom, Message
from api.user.services import message_service
from api.user.services.cmds import (
    CreateMessageCmd,
    DeleteMessageCmd,
    GetMessageCmd,
    ListMessagesQuery,
)


async def _make_room(test_user) -> ChatRoom:
    return await ChatRoom.objects.acreate(name="test-room", created_by=test_user)


def _create_cmd(sender_id: int, room_id: int, content: str) -> CreateMessageCmd:
    return CreateMessageCmd(sender_id=sender_id, room_id=room_id, content=content)


@pytest.mark.django_db(transaction=True)
class TestMessageService:
    async def test_create_message(self, test_user) -> None:
        room = await _make_room(test_user)
        message = await message_service.create_message(
            _create_cmd(test_user.id, room.id, "Hello"),
        )
        assert message.content == "Hello"
        assert message.sender_id == test_user.id
        assert message.room_id == room.id
        assert await Message.objects.filter(id=message.id).aexists()

    async def test_create_message_touches_room(self, test_user) -> None:
        room = await _make_room(test_user)
        before = room.updated_at
        await message_service.create_message(_create_cmd(test_user.id, room.id, "Hello"))
        refreshed = await ChatRoom.objects.aget(id=room.id)
        assert refreshed.updated_at > before

    async def test_get_message(self, test_user) -> None:
        room = await _make_room(test_user)
        message = await message_service.create_message(
            _create_cmd(test_user.id, room.id, "Hello"),
        )
        fetched = await message_service.get_message(
            GetMessageCmd(message_id=message.id),
        )
        assert fetched is not None
        assert fetched.sender.username == test_user.username

    async def test_get_message_missing(self) -> None:
        message = await message_service.get_message(GetMessageCmd(message_id=999_999))
        assert message is None

    async def test_delete_message(self, test_user) -> None:
        room = await _make_room(test_user)
        message = await message_service.create_message(
            _create_cmd(test_user.id, room.id, "Hello"),
        )
        deleted = await message_service.delete_message(
            DeleteMessageCmd(message_id=message.id),
        )
        assert deleted is True
        assert await Message.objects.filter(id=message.id).aexists() is False

    async def test_queryset_search(self, test_user) -> None:
        room = await _make_room(test_user)
        await message_service.create_message(
            _create_cmd(test_user.id, room.id, "Hello world"),
        )
        await message_service.create_message(
            _create_cmd(test_user.id, room.id, "Other text"),
        )

        qs = message_service.message_queryset(ListMessagesQuery(search="hello"))
        matches = [message async for message in qs]
        assert len(matches) == 1  # content__icontains -> matches "Hello world"

    async def test_queryset_room_filter(self, test_user) -> None:
        room_a = await _make_room(test_user)
        room_b = await ChatRoom.objects.acreate(name="other", created_by=test_user)
        await message_service.create_message(
            _create_cmd(test_user.id, room_a.id, "in a"),
        )
        await message_service.create_message(
            _create_cmd(test_user.id, room_b.id, "in b"),
        )

        qs = message_service.message_queryset(ListMessagesQuery(room_id=room_a.id))
        messages = [message async for message in qs]
        assert len(messages) == 1
        assert messages[0].content == "in a"

    async def test_queryset_sort_desc_is_default(self, test_user) -> None:
        room = await _make_room(test_user)
        first = await message_service.create_message(
            _create_cmd(test_user.id, room.id, "first"),
        )
        second = await message_service.create_message(
            _create_cmd(test_user.id, room.id, "second"),
        )

        qs = message_service.message_queryset(ListMessagesQuery(sort="desc"))
        messages = [message async for message in qs]
        assert [message.id for message in messages] == [second.id, first.id]

    async def test_queryset_sort_asc(self, test_user) -> None:
        room = await _make_room(test_user)
        first = await message_service.create_message(
            _create_cmd(test_user.id, room.id, "first"),
        )
        second = await message_service.create_message(
            _create_cmd(test_user.id, room.id, "second"),
        )

        qs = message_service.message_queryset(ListMessagesQuery(sort="asc"))
        messages = [message async for message in qs]
        assert [message.id for message in messages] == [first.id, second.id]
