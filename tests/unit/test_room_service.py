# tests/unit/test_room_service.py
from __future__ import annotations

import pytest

from api.common.exceptions import PermissionDeniedError
from api.user.models import ChatRoom, RoomMembership, RoomType
from api.user.schema import RoomCreateIn
from api.user.services import room_service


@pytest.mark.django_db(transaction=True)
class TestRoomService:
    async def test_create_room_adds_creator_membership(self, test_user) -> None:
        payload = RoomCreateIn(name="general", is_private=False)
        room = await room_service.create_room(test_user.id, payload)

        assert room.name == "general"
        assert room.room_type == RoomType.GROUP
        assert await RoomMembership.objects.filter(
            room=room,
            user=test_user,
        ).aexists()

    async def test_get_room(self, test_user) -> None:
        room = await ChatRoom.objects.acreate(name="r1", created_by=test_user)
        fetched = await room_service.get_room(room.id)
        assert fetched is not None
        assert fetched.id == room.id

    async def test_get_room_missing(self) -> None:
        assert await room_service.get_room(999_999) is None

    async def test_get_or_create_direct_room_idempotent(self, test_user) -> None:
        other = await ChatRoom._meta.apps.get_model("user", "User").objects.acreate(
            username="peer",
            email="peer@example.com",
            password="x",
        )
        first = await room_service.get_or_create_direct_room(test_user.id, other.id)
        second = await room_service.get_or_create_direct_room(other.id, test_user.id)

        assert first.id == second.id
        assert first.room_type == RoomType.DIRECT
        assert first.is_private is True
        assert await RoomMembership.objects.filter(room=first).acount() == 2

    async def test_join_public_room(self, test_user) -> None:
        owner = test_user
        room = await ChatRoom.objects.acreate(name="pub", created_by=owner)
        joiner = await ChatRoom._meta.apps.get_model("user", "User").objects.acreate(
            username="joiner",
            email="joiner@example.com",
            password="x",
        )

        joined = await room_service.join_room(room.id, joiner.id)

        assert joined is True
        assert await room_service.is_member(room.id, joiner.id)

    async def test_join_private_room_denied(self, test_user) -> None:
        room = await ChatRoom.objects.acreate(
            name="priv",
            created_by=test_user,
            is_private=True,
        )
        with pytest.raises(PermissionDeniedError):
            await room_service.join_room(room.id, test_user.id)

    async def test_join_missing_room(self, test_user) -> None:
        assert await room_service.join_room(999_999, test_user.id) is False


@pytest.mark.django_db(transaction=True)
class TestLeaveRoom:
    async def test_leave_room(self, test_user) -> None:
        room = await _make_membership_room(test_user)

        left = await room_service.leave_room(room.id, test_user.id)

        assert left is True
        assert not await room_service.is_member(room.id, test_user.id)

    async def test_leave_missing_room(self, test_user) -> None:
        assert await room_service.leave_room(999_999, test_user.id) is False


async def _make_membership_room(user) -> ChatRoom:
    room = await ChatRoom.objects.acreate(name="leave-me", created_by=user)
    await RoomMembership.objects.acreate(room=room, user=user)
    return room
