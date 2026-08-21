# tests/integration/test_chat_views.py
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from api.user.models import ChatRoom, Message, RoomMembership

if TYPE_CHECKING:
    from django.test import AsyncClient

_USER_PASSWORD = "testpass123"


async def _make_room_with_member(user) -> ChatRoom:
    """Create a room and add the user as a member."""
    room = await ChatRoom.objects.acreate(name="test-room", created_by=user)
    await RoomMembership.objects.acreate(room=room, user=user)
    return room


async def _login(async_client: AsyncClient, username: str) -> None:
    """Log in via the session login flow."""
    resp = await async_client.post(
        "/login/",
        {"username": username, "password": _USER_PASSWORD},
    )
    assert resp.status_code == 302


@pytest.mark.django_db(transaction=True)
class TestChatPage:
    """Chat page and authentication."""

    async def test_chat_page_redirects_anonymous(self, async_client: AsyncClient) -> None:
        """Anonymous users are redirected to the login page."""
        resp = await async_client.get("/chat/")
        assert resp.status_code == 302
        assert "/login/" in resp.headers["Location"]

    async def test_chat_page_renders_form_and_messages(
        self,
        async_client: AsyncClient,
        test_user,
    ) -> None:
        """Authenticated users see the form and existing messages."""
        await _login(async_client, test_user.username)
        room = await _make_room_with_member(test_user)
        await Message.objects.acreate(
            sender=test_user,
            room=room,
            content="hello chat",
        )

        resp = await async_client.get("/chat/")

        assert resp.status_code == 200
        assert "message-form" in resp.content.decode()
        assert "hello chat" in resp.content.decode()
        assert test_user.username in resp.content.decode()


@pytest.mark.django_db(transaction=True)
class TestSendMessage:
    """REST endpoint for creating messages."""

    async def test_send_requires_auth(self, async_client: AsyncClient) -> None:
        """Anonymous POST is redirected to login."""
        resp = await async_client.post("/chat/send/", {"content": "nope"})
        assert resp.status_code == 302
        assert "/login/" in resp.headers["Location"]

    async def test_send_creates_message(
        self,
        async_client: AsyncClient,
        test_user,
    ) -> None:
        """Authenticated POST creates a message and returns its JSON."""
        await _login(async_client, test_user.username)

        resp = await async_client.post("/chat/send/", {"content": "hello rest"})

        assert resp.status_code == 201
        payload = resp.json()
        assert payload["content"] == "hello rest"
        assert payload["sender"] == test_user.username
        assert await Message.objects.acount() == 1

    async def test_send_empty_rejected(
        self,
        async_client: AsyncClient,
        test_user,
    ) -> None:
        """Empty content returns a 400 with field errors."""
        await _login(async_client, test_user.username)

        resp = await async_client.post("/chat/send/", {"content": ""})

        assert resp.status_code == 400
        assert "errors" in resp.json()
        assert await Message.objects.acount() == 0


@pytest.mark.django_db(transaction=True)
class TestMessageStream:
    """SSE streaming endpoint."""

    async def test_stream_requires_auth(self, async_client: AsyncClient) -> None:
        """Anonymous stream request is redirected to login."""
        resp = await async_client.get("/chat/stream/")
        assert resp.status_code == 302
        assert "/login/" in resp.headers["Location"]

    async def test_stream_yields_rendered_message(
        self,
        async_client: AsyncClient,
        test_user,
    ) -> None:
        """The stream emits a rendered message partial for new messages."""
        await _login(async_client, test_user.username)
        message = await Message.objects.acreate(
            sender=test_user,
            room=await _make_room_with_member(test_user),
            content="hello sse",
        )

        resp = await async_client.get("/chat/stream/")

        assert resp.status_code == 200
        assert resp["Content-Type"] == "text/event-stream"
        chunk = await resp.streaming_content.__anext__()
        assert b"event: message" in chunk
        assert b"hello sse" in chunk
        assert b"id: %d" % message.id in chunk
