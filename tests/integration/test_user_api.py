# tests/integration/test_user_api.py
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart

from api.common.lockout import MAX_FAILED_LOGINS
from api.user.limits import MAX_PHOTO_SIZE_BYTES
from api.user.models import Message

if TYPE_CHECKING:
    from django.http import HttpResponse

User = get_user_model()


async def _register_user(dmr_async_client, user_data: dict[str, str]) -> None:
    resp = await dmr_async_client.post(
        "/api/user/users",
        data=user_data,
        content_type="application/json",
    )
    assert resp.status_code == 201, resp.json()


async def _get_token(dmr_async_client, username: str, password: str) -> str:
    resp = await dmr_async_client.post(
        "/api/user/token",
        data={"username": username, "password": password},
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.json()
    return resp.json()["access_token"]


async def _create_room(dmr_async_client, token: str) -> int:
    resp = await dmr_async_client.post(
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
        dmr_async_client,
        user_data: dict[str, str],
    ) -> None:
        resp = await dmr_async_client.post(
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
        dmr_async_client,
        user_data: dict[str, str],
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        resp = await dmr_async_client.post(
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
        dmr_async_client,
        user_data: dict[str, str],
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        resp = await dmr_async_client.get(
            "/api/user/users/999999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert _error_type(body) == "not_found"

    async def test_users_pagination(
        self,
        dmr_async_client,
        user_data: dict[str, str],
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        resp = await dmr_async_client.get(
            "/api/user/users?page=1&page_size=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "count" in body
        assert "object_list" in body["page"]
        assert body["count"] >= 1

    async def test_token_invalid_credentials(self, dmr_async_client) -> None:
        resp = await dmr_async_client.post(
            "/api/user/token",
            data={"username": "nobody", "password": "wrong"},
            content_type="application/json",
        )
        assert resp.status_code == 401
        assert _error_type(resp.json()) == "security"

    async def test_get_me(self, dmr_async_client, user_data: dict[str, str]) -> None:
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        resp = await dmr_async_client.get(
            "/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == user_data["username"]

    async def test_update_user_own_profile(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        me = await dmr_async_client.get(
            "/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = me.json()["id"]

        resp = await dmr_async_client.put(
            f"/api/user/users/{user_id}",
            data={"first_name": "UpdatedName"},
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["first_name"] == "UpdatedName"

    async def test_update_user_explicit_null_rejected(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        me = await dmr_async_client.get(
            "/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = me.json()["id"]

        resp = await dmr_async_client.put(
            f"/api/user/users/{user_id}",
            data={"first_name": None},
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"][0]["loc"][-1] == "first_name"

        still_there = await dmr_async_client.get(
            "/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert still_there.json()["first_name"] == user_data["first_name"]

    async def test_update_user_duplicate_email(
        self, dmr_async_client, user_data: dict[str, str], user_data2
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        await _register_user(dmr_async_client, user_data2)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        me = await dmr_async_client.get(
            "/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = me.json()["id"]

        resp = await dmr_async_client.put(
            f"/api/user/users/{user_id}",
            data={"email": user_data2["email"]},
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409
        assert _error_type(resp.json()) == "conflict"

    async def test_update_user_forbidden(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )

        resp = await dmr_async_client.put(
            "/api/user/users/999999",
            data={"first_name": "Hacked"},
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert _error_type(resp.json()) == "permission_denied"

    async def test_delete_user_own(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        me = await dmr_async_client.get(
            "/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = me.json()["id"]

        resp = await dmr_async_client.delete(
            f"/api/user/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204
        assert await User.objects.filter(id=user_id).aexists() is False

    async def test_delete_user_forbidden(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )

        resp = await dmr_async_client.delete(
            "/api/user/users/999999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_room_membership_join_leave(
        self, dmr_async_client, user_data: dict[str, str], user_data2
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        await _register_user(dmr_async_client, user_data2)
        token1 = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        token2 = await _get_token(
            dmr_async_client,
            user_data2["username"],
            user_data2["password"],
        )
        room_id = await _create_room(dmr_async_client, token1)

        joined = await dmr_async_client.post(
            f"/api/user/rooms/{room_id}/membership",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert joined.status_code == 204

        left = await dmr_async_client.delete(
            f"/api/user/rooms/{room_id}/membership",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert left.status_code == 204

        missing = await dmr_async_client.post(
            "/api/user/rooms/999999/membership",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert missing.status_code == 404

    async def test_refresh_token_rotation(self, dmr_async_client, user_data) -> None:
        await _register_user(dmr_async_client, user_data)
        token_resp = await dmr_async_client.post(
            "/api/user/token",
            data={"username": user_data["username"], "password": user_data["password"]},
            content_type="application/json",
        )
        tokens = token_resp.json()

        first = await dmr_async_client.post(
            "/api/user/refresh",
            data={"refresh_token": tokens["refresh_token"]},
            content_type="application/json",
        )
        assert first.status_code == 200
        assert "access_token" in first.json()

        replay = await dmr_async_client.post(
            "/api/user/refresh",
            data={"refresh_token": tokens["refresh_token"]},
            content_type="application/json",
        )
        assert replay.status_code == 401
        # RFC 9110: every 401 advertises the scheme to use.
        assert replay.headers["WWW-Authenticate"] == "Bearer"

    async def test_refresh_broken_token_rejected(self, dmr_async_client) -> None:
        """A malformed refresh token answers 401 JSON, not a 500 crash."""
        resp = await dmr_async_client.post(
            "/api/user/refresh",
            data={"refresh_token": "not-a-jwt-at-all"},
            content_type="application/json",
        )
        assert resp.status_code == 401, resp.content
        assert resp.headers["WWW-Authenticate"] == "Bearer"
        assert _error_type(resp.json()) == "security"

    async def test_refresh_expired_token_rejected(self, dmr_async_client) -> None:
        """An expired refresh token answers 401 JSON, not a 500 crash."""
        from datetime import UTC, datetime, timedelta

        import jwt as pyjwt
        from django.conf import settings

        now = datetime.now(UTC)
        expired = pyjwt.encode(
            {
                "sub": "1",
                "jti": "expired-test-jti",
                "extras": {"type": "refresh"},
                "exp": int((now - timedelta(minutes=1)).timestamp()),
                "iat": int((now - timedelta(minutes=10)).timestamp()),
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        resp = await dmr_async_client.post(
            "/api/user/refresh",
            data={"refresh_token": expired},
            content_type="application/json",
        )
        assert resp.status_code == 401, resp.content
        assert resp.headers["WWW-Authenticate"] == "Bearer"

    async def test_create_message(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )

        headers = {"Authorization": f"Bearer {token}"}
        room_id = await _create_room(dmr_async_client, token)

        resp = await dmr_async_client.post(
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
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        headers = {"Authorization": f"Bearer {token}"}
        room_id = await _create_room(dmr_async_client, token)

        await dmr_async_client.post(
            "/api/user/messages",
            data={"room_id": room_id, "content": "unique needle"},
            content_type="application/json",
            headers=headers,
        )
        resp = await dmr_async_client.get(
            f"/api/user/messages?search=needle&room_id={room_id}&limit=10",
            headers=headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["page"]) >= 1

    async def test_message_cursor_pagination(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        """Keyset pages never skip or duplicate rows, unlike page numbers."""
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        headers = {"Authorization": f"Bearer {token}"}
        room_id = await _create_room(dmr_async_client, token)

        created_ids: list[int] = []
        for index in range(3):
            resp = await dmr_async_client.post(
                "/api/user/messages",
                data={"room_id": room_id, "content": f"message {index}"},
                content_type="application/json",
                headers=headers,
            )
            created_ids.append(resp.json()["id"])

        first = await dmr_async_client.get(
            f"/api/user/messages?room_id={room_id}&limit=2&sort=asc",
            headers=headers,
        )
        assert first.status_code == 200
        first_body = first.json()
        assert [item["id"] for item in first_body["page"]] == created_ids[:2]
        assert first_body["next_cursor"] is not None

        second = await dmr_async_client.get(
            "/api/user/messages"
            f"?room_id={room_id}&limit=2&sort=asc"
            f"&cursor={first_body['next_cursor']}",
            headers=headers,
        )
        assert second.status_code == 200
        second_body = second.json()
        # The full walk covers every message exactly once.
        assert [item["id"] for item in second_body["page"]] == created_ids[2:]
        assert second_body["next_cursor"] is None

    async def test_message_invalid_cursor_rejected(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        """A malformed cursor answers a documented 400, not a 500."""
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        resp = await dmr_async_client.get(
            "/api/user/messages?cursor=not-a-valid-cursor",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400, resp.content
        assert _error_type(resp.json()) == "invalid_cursor"

    async def test_delete_message_own(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        headers = {"Authorization": f"Bearer {token}"}
        room_id = await _create_room(dmr_async_client, token)

        created = await dmr_async_client.post(
            "/api/user/messages",
            data={"room_id": room_id, "content": "delete me"},
            content_type="application/json",
            headers=headers,
        )
        message_id = created.json()["id"]

        resp = await dmr_async_client.delete(
            f"/api/user/messages/{message_id}",
            headers=headers,
        )
        assert resp.status_code == 204
        assert await Message.objects.filter(id=message_id).aexists() is False

    async def test_delete_message_forbidden(
        self, dmr_async_client, user_data: dict[str, str], user_data2
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        await _register_user(dmr_async_client, user_data2)
        token1 = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        token2 = await _get_token(
            dmr_async_client,
            user_data2["username"],
            user_data2["password"],
        )

        room_id = await _create_room(dmr_async_client, token1)
        created = await dmr_async_client.post(
            "/api/user/messages",
            data={"room_id": room_id, "content": "mine"},
            content_type="application/json",
            headers={"Authorization": f"Bearer {token1}"},
        )
        message_id = created.json()["id"]

        resp = await dmr_async_client.delete(
            f"/api/user/messages/{message_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert resp.status_code == 403

    async def test_delete_message_not_found(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        token = await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        resp = await dmr_async_client.delete(
            "/api/user/messages/999999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
        assert _error_type(resp.json()) == "not_found"

    async def test_me_requires_auth(self, dmr_async_client) -> None:
        resp = await dmr_async_client.get("/api/user/me")
        assert resp.status_code == 401


@pytest.mark.django_db(transaction=True)
class TestPhotoApi:
    async def _token(self, dmr_async_client, user_data: dict[str, str]) -> str:
        await _register_user(dmr_async_client, user_data)
        return await _get_token(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )

    async def _upload(
        self,
        dmr_async_client,
        token: str,
        files: dict[str, object],
    ) -> HttpResponse:
        return await dmr_async_client.post(
            "/api/user/photos",
            data=encode_multipart(BOUNDARY, files),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": MULTIPART_CONTENT,
            },
        )

    async def test_upload_photo_success(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        token = await self._token(dmr_async_client, user_data)
        image = SimpleUploadedFile(
            "photo.png",
            b"\x89PNG\r\n\x1a\nfake-image",
            content_type="image/png",
        )

        resp = await self._upload(dmr_async_client, token, {"image": image})

        assert resp.status_code == 201, resp.json()
        assert resp.json()["image"].endswith(".png")

    async def test_upload_photo_rejects_non_image(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        token = await self._token(dmr_async_client, user_data)
        notes = SimpleUploadedFile("notes.txt", b"just text", content_type="text/plain")

        resp = await self._upload(dmr_async_client, token, {"image": notes})

        assert resp.status_code == 400, resp.json()
        assert resp.json()["detail"][0]["loc"] == [
            "parsed_file_metadata",
            "image",
            "content_type",
        ]

    async def test_upload_photo_rejects_oversized(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        token = await self._token(dmr_async_client, user_data)
        oversized = SimpleUploadedFile(
            "big.png",
            b"\0" * (MAX_PHOTO_SIZE_BYTES + 1),
            content_type="image/png",
        )

        resp = await self._upload(dmr_async_client, token, {"image": oversized})

        assert resp.status_code == 400, resp.json()
        assert resp.json()["detail"][0]["loc"] == [
            "parsed_file_metadata",
            "image",
            "size",
        ]

    async def test_upload_photo_requires_file(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        token = await self._token(dmr_async_client, user_data)

        resp = await self._upload(dmr_async_client, token, {})

        assert resp.status_code == 400, resp.json()
        assert resp.json()["detail"][0]["loc"][-1] == "image"


@pytest.mark.django_db(transaction=True)
class TestLoginLockout:
    async def _login(
        self,
        dmr_async_client,
        username: str,
        password: str,
    ) -> HttpResponse:
        return await dmr_async_client.post(
            "/api/user/token",
            data={"username": username, "password": password},
        )

    async def test_lockout_after_failed_logins(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(dmr_async_client, user_data)

        for _ in range(MAX_FAILED_LOGINS):
            failed = await self._login(
                dmr_async_client,
                user_data["username"],
                "definitely-wrong",
            )
            assert failed.status_code == 401
            assert failed.headers["WWW-Authenticate"] == "Bearer"

        locked = await self._login(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )

        assert locked.status_code == 429
        assert _error_type(locked.json()) == "rate_limited"
        # Lockout answers with the same rate-limit headers as the throttle.
        assert locked.headers["X-RateLimit-Limit"] == str(MAX_FAILED_LOGINS)
        assert locked.headers["X-RateLimit-Remaining"] == "0"
        assert int(locked.headers["Retry-After"]) > 0

    async def test_successful_login_resets_failures(
        self, dmr_async_client, user_data: dict[str, str]
    ) -> None:
        await _register_user(dmr_async_client, user_data)
        await self._login(dmr_async_client, user_data["username"], "definitely-wrong")

        first = await self._login(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        assert first.status_code == 200

        for _ in range(MAX_FAILED_LOGINS - 1):
            failed = await self._login(
                dmr_async_client,
                user_data["username"],
                "definitely-wrong",
            )
            assert failed.status_code == 401
            assert failed.headers["WWW-Authenticate"] == "Bearer"

        second = await self._login(
            dmr_async_client,
            user_data["username"],
            user_data["password"],
        )
        assert second.status_code == 200
