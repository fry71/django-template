# tests/unit/test_message_service.py
from __future__ import annotations

import pytest

from api.user.models import Message
from api.user.services import message_service


@pytest.mark.django_db(transaction=True)
class TestMessageService:
    async def test_create_message(self, test_user) -> None:
        message = await message_service.create_message(test_user.id, "Hello")
        assert message.content == "Hello"
        assert message.sender_id == test_user.id
        assert await Message.objects.filter(id=message.id).aexists()

    async def test_get_message(self, test_user) -> None:
        message = await message_service.create_message(test_user.id, "Hello")
        fetched = await message_service.get_message(message.id)
        assert fetched is not None
        assert fetched.sender.username == test_user.username

    async def test_get_message_missing(self) -> None:
        message = await message_service.get_message(999_999)
        assert message is None

    async def test_delete_message(self, test_user) -> None:
        message = await message_service.create_message(test_user.id, "Hello")
        deleted = await message_service.delete_message(message.id)
        assert deleted is True
        assert await Message.objects.filter(id=message.id).aexists() is False

    async def test_queryset_search(self, test_user) -> None:
        await message_service.create_message(test_user.id, "Hello world")
        await message_service.create_message(test_user.id, "Other text")

        qs = message_service.message_queryset(search="hello")
        assert [m async for m in qs]  # content__icontains -> matches "Hello world"
