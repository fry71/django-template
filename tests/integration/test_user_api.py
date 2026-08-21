# tests/integration/test_user_api.py
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from api.user.models import Message

User = get_user_model()


async def _register_user(async_client, user_data: dict[str, str]) -> None:
    resp = await async_client.post(
        "/api/user/users",
        data=user_data,
        content_type="application/json",
    )
    assert resp.status_code == 201, resp.json()


async def _get_token(async_client, username: str, password: str) -> str:
    resp = await async_client.post(
        "/api/user/token",
        data={"username": username, "password": password},
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


async def _create_room(async_client, token: str) -> int:
    resp = await async_client.post(
        "/api/user/rooms",
        data={"name": "test-room"},
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()["id"]


def _error_type(body: dict[str, object]) -> str:
    """Return the machine-readable error type from a DMR ErrorModel."""
    detail = body["detail"]
    assert isinstance(detail, list)
    return str(detail[0]["type"])


@pytest.mark.django_db(transaction=True)
class TestUserApi:
    async def test_create_user_success(
        self,
        async_client,
        user_data: dict[str, str],
    ) -> None:
        resp = await async_client.post(
            "/api/user/users",
            data=user_data,
            content_type="application/json",
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["username"] == user_data["username"]
        assert body["email"] == user_data["email"]

    async def test_create_user_duplicate_email(
        self,
        async_client,
        user_data: dict[str, str],
    ) -> None:
        await _register_user(async_client, user_data)
        resp = await async_client.post(
            "/api/user/users",
            data=user_data,
            content_type="application/json",
        )
        assert resp.status_code == 409
        body = resp.json()
        assert _error_type(body) == "conflict"
        assert body["detail"][0]["msg"] == "Email already exists"

    async def test_get_user_not_found(
        self,
        async_client,
        user_data: dict[str, str],
    ) -> None:
        await _register_user(async_client, user_data)
        token = await _get_token(
            async_client,
            user_data["username"],
            user_data["password"],
        )
        resp = await async_client.get(
            "/api/user/users/999999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert _error_type(body) == "not_found"

    async def test_users_pagination(
        self,
        async_client,
        user_data: dict[str, str],
    ) -> None:
        await _register_user(async_client, user_data)
        token = await _get_token(
            async_client,
            user_data["username"],
            user_data["password"],
        )
        resp = await async_client.get(
            "/api/user/users?page=1&page_size=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "count" in body
        assert "object_list" in body["page"]
        assert body["count"] >= 1

    async def test_token_invalid_credentials(self, async_client) -> None:
        resp = await async_client.post(
            "/api/user/token",
            data={"username": "nobody", "password": "wrong"},
            content_type="application/json",
        )
        assert resp.status_code == 401
        assert _error_type(resp.json()) == "security"

    async def test_get_me(self, async_client, user_data: dict[str, str]) -> None:
        await _register_user(async_client, user_data)
        token = await _get_token(
            async_client,
            user_data["username"],
            user_data["password"],
        )
        resp = await async_client.get(
            "/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == user_data["username"]

    async def test_update_user_own_profile(
        self, async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(async_client, user_data)
        token = await _get_token(
            async_client,
            user_data["username"],
            user_data["password"],
        )
        me = await async_client.get(
            "/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = me.json()["id"]

        resp = await async_client.put(
            f"/api/user/users/{user_id}",
            data={"first_name": "UpdatedName"},
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["first_name"] == "UpdatedName"

    async def test_update_user_duplicate_email(
        self, async_client, user_data: dict[str, str], user_data2
    ) -> None:
        await _register_user(async_client, user_data)
        await _register_user(async_client, user_data2)
        token = await _get_token(
            async_client,
            user_data["username"],
            user_data["password"],
        )
        me = await async_client.get(
            "/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = me.json()["id"]

        resp = await async_client.put(
            f"/api/user/users/{user_id}",
            data={"email": user_data2["email"]},
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409
        assert _error_type(resp.json()) == "conflict"

    async def test_update_user_forbidden(
        self, async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(async_client, user_data)
        token = await _get_token(
            async_client,
            user_data["username"],
            user_data["password"],
        )

        resp = await async_client.put(
            "/api/user/users/999999",
            data={"first_name": "Hacked"},
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert _error_type(resp.json()) == "permission_denied"

    async def test_delete_user_own(self, async_client, user_data: dict[str, str]) -> None:
        await _register_user(async_client, user_data)
        token = await _get_token(
            async_client,
            user_data["username"],
            user_data["password"],
        )
        me = await async_client.get(
            "/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = me.json()["id"]

        resp = await async_client.delete(
            f"/api/user/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204
        assert await User.objects.filter(id=user_id).aexists() is False

    async def test_delete_user_forbidden(
        self, async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(async_client, user_data)
        token = await _get_token(
            async_client,
            user_data["username"],
            user_data["password"],
        )

        resp = await async_client.delete(
            "/api/user/users/999999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_refresh_token_rotation(self, async_client, user_data) -> None:
        await _register_user(async_client, user_data)
        token_resp = await async_client.post(
            "/api/user/token",
            data={"username": user_data["username"], "password": user_data["password"]},
            content_type="application/json",
        )
        tokens = token_resp.json()

        first = await async_client.post(
            "/api/user/refresh",
            data={"refresh_token": tokens["refresh_token"]},
            content_type="application/json",
        )
        assert first.status_code == 200
        assert "access_token" in first.json()

        replay = await async_client.post(
            "/api/user/refresh",
            data={"refresh_token": tokens["refresh_token"]},
            content_type="application/json",
        )
        assert replay.status_code == 401

    async def test_create_message(self, async_client, user_data: dict[str, str]) -> None:
        await _register_user(async_client, user_data)
        token = await _get_token(
            async_client,
            user_data["username"],
            user_data["password"],
        )

        headers = {"Authorization": f"Bearer {token}"}
        room_id = await _create_room(async_client, token)

        resp = await async_client.post(
            "/api/user/messages",
            data={"room_id": room_id, "content": "Hello!"},
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["content"] == "Hello!"
        assert body["sender"] == user_data["username"]

    async def test_get_messages_search(
        self, async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(async_client, user_data)
        token = await _get_token(
            async_client,
            user_data["username"],
            user_data["password"],
        )
        headers = {"Authorization": f"Bearer {token}"}
        room_id = await _create_room(async_client, token)

        await async_client.post(
            "/api/user/messages",
            data={"room_id": room_id, "content": "unique needle"},
            content_type="application/json",
            headers=headers,
        )
        resp = await async_client.get(
            f"/api/user/messages?search=needle&room_id={room_id}&page=1&page_size=10",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    async def test_delete_message_own(
        self, async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(async_client, user_data)
        token = await _get_token(
            async_client,
            user_data["username"],
            user_data["password"],
        )
        headers = {"Authorization": f"Bearer {token}"}
        room_id = await _create_room(async_client, token)

        created = await async_client.post(
            "/api/user/messages",
            data={"room_id": room_id, "content": "delete me"},
            content_type="application/json",
            headers=headers,
        )
        message_id = created.json()["id"]

        resp = await async_client.delete(
            f"/api/user/messages/{message_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Message deleted"
        assert await Message.objects.filter(id=message_id).aexists() is False

    async def test_delete_message_forbidden(
        self, async_client, user_data: dict[str, str], user_data2
    ) -> None:
        await _register_user(async_client, user_data)
        await _register_user(async_client, user_data2)
        token1 = await _get_token(
            async_client,
            user_data["username"],
            user_data["password"],
        )
        token2 = await _get_token(
            async_client,
            user_data2["username"],
            user_data2["password"],
        )

        room_id = await _create_room(async_client, token1)
        created = await async_client.post(
            "/api/user/messages",
            data={"room_id": room_id, "content": "mine"},
            content_type="application/json",
            headers={"Authorization": f"Bearer {token1}"},
        )
        message_id = created.json()["id"]

        resp = await async_client.delete(
            f"/api/user/messages/{message_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert resp.status_code == 403

    async def test_delete_message_not_found(
        self, async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(async_client, user_data)
        token = await _get_token(
            async_client,
            user_data["username"],
            user_data["password"],
        )
        resp = await async_client.delete(
            "/api/user/messages/999999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
        assert _error_type(resp.json()) == "not_found"

    async def test_me_requires_auth(self, async_client) -> None:
        resp = await async_client.get("/api/user/me")
        assert resp.status_code == 401
