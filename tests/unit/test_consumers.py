# tests/unit/test_consumers.py
from __future__ import annotations

import json
from datetime import UTC

import pytest

from api.user.consumers import ChatConsumer
from api.user.models import ChatRoom, Message, RoomMembership


class _FakeChannelLayer:
    def __init__(self) -> None:
        self.groups: list[tuple[str, str]] = []
        self.sent: list[dict] = []

    async def group_add(self, group: str, channel: str) -> None:
        self.groups.append((group, channel))

    async def group_discard(self, group: str, channel: str) -> None:
        if (group, channel) in self.groups:
            self.groups.remove((group, channel))

    async def group_send(self, group: str, event: dict) -> None:
        self.sent.append(event)


async def _make_consumer(token: str | None, room_id: int | None = 1) -> ChatConsumer:
    consumer = ChatConsumer.__new__(ChatConsumer)
    consumer.scope = {
        "url_route": {"kwargs": {"token": token, "room_id": room_id}},
    }
    consumer.channel_layer = _FakeChannelLayer()
    consumer.channel_name = "test_channel"
    consumer._sent_messages: list[dict] = []

    async def base_send(message: dict) -> None:
        consumer._sent_messages.append(message)

    consumer.base_send = base_send
    return consumer


async def _make_room(user, *, member: bool = True) -> ChatRoom:
    room = await ChatRoom.objects.acreate(
        name="test-room",
        created_by=user,
    )
    if member:
        await RoomMembership.objects.acreate(room=room, user=user)
    return room


async def _make_valid_token(user) -> str:
    from datetime import datetime, timedelta

    import jwt as pyjwt
    from django.conf import settings

    now = datetime.now(UTC)
    payload = {
        "user_id": user.id,
        "token_type": "access",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "iat": int(now.timestamp()),
    }
    return pyjwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


@pytest.mark.django_db(transaction=True)
class TestChatConsumerConnect:
    async def test_connect_success(self, test_user) -> None:
        room = await _make_room(test_user)
        consumer = await _make_consumer(await _make_valid_token(test_user), room.id)
        accepted: list[bool] = []

        async def fake_accept() -> None:
            accepted.append(True)

        async def fake_close() -> None:
            raise AssertionError("connect should not close")

        consumer.accept = fake_accept  # type: ignore[method-assign]
        consumer.close = fake_close  # type: ignore[method-assign]

        await consumer.connect()

        assert accepted == [True]
        assert consumer.user.id == test_user.id
        assert consumer.group_name == f"chat_{room.id}"
        assert consumer.channel_layer.groups == [
            (f"chat_{room.id}", "test_channel"),
        ]

    async def test_connect_non_member_rejected(self, test_user) -> None:
        room = await _make_room(test_user, member=False)
        consumer = await _make_consumer(await _make_valid_token(test_user), room.id)
        closed: list[bool] = []

        async def fake_close() -> None:
            closed.append(True)

        async def fake_accept() -> None:
            raise AssertionError("should not accept non-member")

        consumer.accept = fake_accept  # type: ignore[method-assign]
        consumer.close = fake_close  # type: ignore[method-assign]

        await consumer.connect()

        assert closed == [True]

    async def test_connect_without_token(self, test_user) -> None:
        await _make_room(test_user)
        consumer = await _make_consumer(None)
        closed: list[bool] = []

        async def fake_close() -> None:
            closed.append(True)

        async def fake_accept() -> None:
            raise AssertionError("should not accept without token")

        consumer.accept = fake_accept  # type: ignore[method-assign]
        consumer.close = fake_close  # type: ignore[method-assign]

        await consumer.connect()

        assert closed == [True]

    async def test_connect_invalid_token(self, test_user) -> None:
        await _make_room(test_user)
        consumer = await _make_consumer("not-a-valid-jwt")
        closed: list[bool] = []

        async def fake_close() -> None:
            closed.append(True)

        async def fake_accept() -> None:
            raise AssertionError("should not accept invalid token")

        consumer.accept = fake_accept  # type: ignore[method-assign]
        consumer.close = fake_close  # type: ignore[method-assign]

        await consumer.connect()

        assert closed == [True]

    async def test_connect_refresh_token_rejected(self, test_user) -> None:
        from datetime import datetime, timedelta

        import jwt as pyjwt
        from django.conf import settings

        await _make_room(test_user)
        now = datetime.now(UTC)
        payload = {
            "user_id": test_user.id,
            "token_type": "refresh",
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "iat": int(now.timestamp()),
        }
        token = pyjwt.encode(
            payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

        consumer = await _make_consumer(token)
        closed: list[bool] = []

        async def fake_close() -> None:
            closed.append(True)

        async def fake_accept() -> None:
            raise AssertionError("should not accept refresh token")

        consumer.accept = fake_accept  # type: ignore[method-assign]
        consumer.close = fake_close  # type: ignore[method-assign]

        await consumer.connect()

        assert closed == [True]

    async def test_connect_user_not_found(self, test_user) -> None:
        from datetime import datetime, timedelta

        import jwt as pyjwt
        from django.conf import settings

        await _make_room(test_user)
        now = datetime.now(UTC)
        payload = {
            "user_id": 999_999,
            "token_type": "access",
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "iat": int(now.timestamp()),
        }
        token = pyjwt.encode(
            payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

        consumer = await _make_consumer(token)
        closed: list[bool] = []

        async def fake_close() -> None:
            closed.append(True)

        async def fake_accept() -> None:
            raise AssertionError("should not accept missing user")

        consumer.accept = fake_accept  # type: ignore[method-assign]
        consumer.close = fake_close  # type: ignore[method-assign]

        await consumer.connect()

        assert closed == [True]


@pytest.mark.django_db(transaction=True)
class TestChatConsumerDisconnect:
    async def test_disconnect_cleans_group(self, test_user) -> None:
        room = await _make_room(test_user)
        consumer = await _make_consumer(await _make_valid_token(test_user), room.id)
        consumer.user = test_user
        consumer.group_name = f"chat_{room.id}"

        await consumer.connect()
        await consumer.disconnect(1000)

        assert consumer.channel_layer.groups == []


@pytest.mark.django_db(transaction=True)
class TestChatConsumerReceive:
    async def test_receive_before_connect(self, test_user) -> None:
        consumer = await _make_consumer(await _make_valid_token(test_user))
        await consumer.receive('{"content": "nope"}')
        assert consumer.channel_layer.sent == []

    async def test_receive_valid_message(self, test_user) -> None:
        room = await _make_room(test_user)
        consumer = await _make_consumer(await _make_valid_token(test_user), room.id)
        await consumer.connect()
        consumer.user = test_user

        await consumer.receive(json.dumps({"content": "hello chat"}))

        assert len(consumer.channel_layer.sent) == 1
        event = consumer.channel_layer.sent[0]
        assert event["type"] == "chat_message"
        assert event["message"]["content"] == "hello chat"
        assert event["message"]["username"] == test_user.username
        assert await Message.objects.filter(
            content="hello chat",
            room_id=room.id,
        ).aexists()

    async def test_receive_empty_content(self, test_user) -> None:
        room = await _make_room(test_user)
        consumer = await _make_consumer(await _make_valid_token(test_user), room.id)
        await consumer.connect()
        consumer.user = test_user

        await consumer.receive(json.dumps({"content": ""}))
        assert consumer.channel_layer.sent == []

    async def test_receive_invalid_json(self, test_user) -> None:
        room = await _make_room(test_user)
        consumer = await _make_consumer(await _make_valid_token(test_user), room.id)
        await consumer.connect()
        consumer.user = test_user

        await consumer.receive("not json {")
        assert consumer.channel_layer.sent == []


@pytest.mark.django_db(transaction=True)
class TestChatConsumerChatMessage:
    async def test_sends_to_client(self) -> None:
        consumer = await _make_consumer(None)
        sent: list[dict] = []

        async def fake_send(text_data: str | None) -> None:
            sent.append(json.loads(text_data))

        consumer.send = fake_send  # type: ignore[method-assign]

        await consumer.chat_message(
            {
                "message": {
                    "content": "from layer",
                    "timestamp": "2026-01-01 10:00",
                    "username": "alice",
                },
            },
        )

        assert sent == [
            {
                "content": "from layer",
                "timestamp": "2026-01-01 10:00",
                "username": "alice",
            },
        ]
