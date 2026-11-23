# tests/integration/test_ws_chat.py
"""End-to-end WebSocket tests through the full ASGI stack.

Unlike the unit tests in tests/unit/test_consumers.py (fake channel layer),
these go through api.web.asgi: real URL routing, real channel layer,
and a dmr-issued access token from the REST login — the exact golden
path documented in AGENTS.md.
"""

from __future__ import annotations

import json

import pytest
from channels.testing import WebsocketCommunicator

from api.user.models import ChatRoom, RoomMembership
from api.web.asgi import application


async def _register_and_login(dmr_async_client, user_data: dict[str, str]) -> str:
    """Register a user and return a real dmr-issued access token."""
    resp = await dmr_async_client.post(
        "/api/user/users",
        data=user_data,
        content_type="application/json",
    )
    assert resp.status_code == 201, resp.json()
    resp = await dmr_async_client.post(
        "/api/user/token",
        data={
            "username": user_data["username"],
            "password": user_data["password"],
        },
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


async def _make_room(dmr_async_client, token: str) -> int:
    """Create a room (the creator becomes a member) and return its id."""
    resp = await dmr_async_client.post(
        "/api/user/rooms",
        data={"name": "ws-room"},
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()["id"]


@pytest.mark.django_db(transaction=True)
class TestChatWebSocketGoldenPath:
    async def test_auth_message_broadcast(
        self,
        dmr_async_client,
        user_data: dict[str, str],
    ) -> None:
        """REST login token auths the socket; messages broadcast back."""
        token = await _register_and_login(dmr_async_client, user_data)
        room_id = await _make_room(dmr_async_client, token)
        room = await ChatRoom.objects.aget(id=room_id)
        # The creator is a member; assert it stays that way for clarity:
        assert await RoomMembership.objects.filter(
            room=room,
            user__username=user_data["username"],
        ).aexists()

        communicator = WebsocketCommunicator(application, f"/ws/chat/{room_id}/")
        try:
            connected, _ = await communicator.connect()
            assert connected

            await communicator.send_to(
                text_data=json.dumps({"type": "auth", "token": token}),
            )
            ack = json.loads(await communicator.receive_from(timeout=5))
            assert ack == {"type": "auth_ok"}

            await communicator.send_to(
                text_data=json.dumps({"content": "hello from ws"}),
            )

            payload = json.loads(await communicator.receive_from(timeout=5))
        finally:
            await communicator.disconnect()

        assert payload["content"] == "hello from ws"
        assert payload["username"] == user_data["username"]

    async def test_invalid_token_closes_socket(
        self,
        dmr_async_client,
        user_data: dict[str, str],
    ) -> None:
        """A broken token closes the socket instead of authenticating it."""
        token = await _register_and_login(dmr_async_client, user_data)
        room_id = await _make_room(dmr_async_client, token)

        communicator = WebsocketCommunicator(application, f"/ws/chat/{room_id}/")
        try:
            connected, _ = await communicator.connect()
            assert connected

            await communicator.send_to(
                text_data=json.dumps({"type": "auth", "token": "garbage"}),
            )
            close_frame = await communicator.receive_output(timeout=5)
        finally:
            await communicator.disconnect()

        assert close_frame["type"] == "websocket.close"
