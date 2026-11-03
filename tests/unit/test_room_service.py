# tests/unit/test_room_service.py
from __future__ import annotations

import pytest

from api.common.exceptions import PermissionDeniedError
from api.user.models import ChatRoom, RoomMembership, RoomType
from api.user.services import room_service
from api.user.services.cmds import (
    CreateRoomCmd,
    EnsureDirectRoomCmd,
    GetRoomCmd,
    IsRoomMemberQuery,
    JoinRoomCmd,
    LeaveRoomCmd,
)


@pytest.mark.django_db(transaction=True)
class TestRoomService:
    async def test_create_room_adds_creator_membership(self, test_user) -> None:
        cmd = CreateRoomCmd(name="general", creator_id=test_user.id)
        room = await room_service.create_room(cmd)

        assert room.name == "general"
        assert room.room_type == RoomType.GROUP
        assert await RoomMembership.objects.filter(
            room=room,
            user=test_user,
        ).aexists()

    async def test_get_room(self, test_user) -> None:
        room = await ChatRoom.objects.acreate(name="r1", created_by=test_user)
        fetched = await room_service.get_room(GetRoomCmd(room_id=room.id))
        assert fetched is not None
        assert fetched.id == room.id

    async def test_get_room_missing(self) -> None:
        assert await room_service.get_room(GetRoomCmd(room_id=999_999)) is None

    async def test_get_or_create_direct_room_idempotent(self, test_user) -> None:
        other = await ChatRoom._meta.apps.get_model("user", "User").objects.acreate(
            username="peer",
            email="peer@example.com",
            password="x",
        )
        first = await room_service.get_or_create_direct_room(
            EnsureDirectRoomCmd(user_a_id=test_user.id, user_b_id=other.id),
        )
        second = await room_service.get_or_create_direct_room(
            EnsureDirectRoomCmd(user_a_id=other.id, user_b_id=test_user.id),
        )

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

        joined = await room_service.join_room(
            JoinRoomCmd(room_id=room.id, user_id=joiner.id),
        )

        assert joined is True
        assert await room_service.is_member(
            IsRoomMemberQuery(room_id=room.id, user_id=joiner.id),
        )

    async def test_join_private_room_denied(self, test_user) -> None:
        room = await ChatRoom.objects.acreate(
            name="priv",
            created_by=test_user,
            is_private=True,
        )
        with pytest.raises(PermissionDeniedError):
            await room_service.join_room(
                JoinRoomCmd(room_id=room.id, user_id=test_user.id),
            )

    async def test_join_missing_room(self, test_user) -> None:
        assert (
            await room_service.join_room(
                JoinRoomCmd(room_id=999_999, user_id=test_user.id),
            )
            is False
        )


@pytest.mark.django_db(transaction=True)
class TestLeaveRoom:
    async def test_leave_room(self, test_user) -> None:
        room = await _make_membership_room(test_user)

        left = await room_service.leave_room(
            LeaveRoomCmd(room_id=room.id, user_id=test_user.id),
        )

        assert left is True
        assert not await room_service.is_member(
            IsRoomMemberQuery(room_id=room.id, user_id=test_user.id),
        )

    async def test_leave_missing_room(self, test_user) -> None:
        assert (
            await room_service.leave_room(
                LeaveRoomCmd(room_id=999_999, user_id=test_user.id),
            )
            is False
        )


async def _make_membership_room(user) -> ChatRoom:
    room = await ChatRoom.objects.acreate(name="leave-me", created_by=user)
    await RoomMembership.objects.acreate(room=room, user=user)
    return room
