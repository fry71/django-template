# tests/unit/test_user_service.py
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from api.common.exceptions import ConflictError, ValidationError
from api.user.schema import UserCreateIn, UserUpdateIn
from api.user.services import user_service

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestCreateUser:
    async def test_create_user_success(self, user_data: dict[str, str]) -> None:
        payload = UserCreateIn(**user_data)
        user = await user_service.create_user(payload)

        assert user.username == user_data["username"]
        assert user.email == user_data["email"]
        assert user.check_password(user_data["password"])
        assert await User.objects.filter(id=user.id).aexists()

    async def test_create_user_duplicate_email(self, user_data: dict[str, str]) -> None:
        await user_service.create_user(UserCreateIn(**user_data))
        with pytest.raises(ConflictError):
            await user_service.create_user(UserCreateIn(**user_data))

    async def test_create_user_invalid_email(self, user_data: dict[str, str]) -> None:
        payload = UserCreateIn(**{**user_data, "email": "not-an-email"})
        with pytest.raises(ValidationError):
            await user_service.create_user(payload)

    async def test_create_user_weak_password(self, user_data: dict[str, str]) -> None:
        # 8 digits pass Pydantic min_length but fail Django NumericPasswordValidator
        payload = UserCreateIn(**{**user_data, "password": "12345678"})
        with pytest.raises(ValidationError):
            await user_service.create_user(payload)


@pytest.mark.django_db(transaction=True)
class TestGetUser:
    async def test_get_user_existing(self, test_user) -> None:
        user = await user_service.get_user(test_user.id)
        assert user is not None
        assert user.id == test_user.id

    async def test_get_user_missing(self) -> None:
        user = await user_service.get_user(999_999)
        assert user is None


@pytest.mark.django_db(transaction=True)
class TestUpdateUser:
    async def test_update_user_partial(self, test_user) -> None:
        payload = UserUpdateIn(first_name="Updated")
        user = await user_service.update_user(test_user.id, payload)

        assert user is not None
        assert user.first_name == "Updated"

    async def test_update_user_missing(self) -> None:
        payload = UserUpdateIn(first_name="Updated")
        user = await user_service.update_user(999_999, payload)
        assert user is None

    async def test_update_user_duplicate_email(self, test_user, user_data) -> None:
        other = await User.objects.acreate_user(
            username="other_user",
            email="other@example.com",
            password="testpass123",
        )
        payload = UserUpdateIn(email=other.email)
        with pytest.raises(ConflictError):
            await user_service.update_user(test_user.id, payload)


@pytest.mark.django_db(transaction=True)
class TestDeleteUser:
    async def test_delete_user_existing(self, test_user) -> None:
        deleted = await user_service.delete_user(test_user.id)
        assert deleted is True
        assert await User.objects.filter(id=test_user.id).aexists() is False

    async def test_delete_user_missing(self) -> None:
        deleted = await user_service.delete_user(999_999)
        assert deleted is False
