# tests/unit/test_user_service.py
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from api.common.exceptions import ConflictError, ValidationError
from api.user.services import user_service
from api.user.services.cmds import (
    CreateUserCmd,
    DeleteUserCmd,
    GetUserCmd,
    UpdateUserCmd,
)

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestCreateUser:
    async def test_create_user_success(self, user_data: dict[str, str]) -> None:
        cmd = CreateUserCmd(**user_data)
        user = await user_service.create_user(cmd)

        assert user.username == user_data["username"]
        assert user.email == user_data["email"]
        assert user.check_password(user_data["password"])
        assert await User.objects.filter(id=user.id).aexists()

    async def test_create_user_duplicate_email(self, user_data: dict[str, str]) -> None:
        await user_service.create_user(CreateUserCmd(**user_data))
        with pytest.raises(ConflictError):
            await user_service.create_user(CreateUserCmd(**user_data))

    async def test_create_user_invalid_email(self, user_data: dict[str, str]) -> None:
        cmd = CreateUserCmd(**{**user_data, "email": "not-an-email"})
        with pytest.raises(ValidationError):
            await user_service.create_user(cmd)

    async def test_create_user_weak_password(self, user_data: dict[str, str]) -> None:
        # 8 digits pass Pydantic min_length but fail Django NumericPasswordValidator
        cmd = CreateUserCmd(**{**user_data, "password": "12345678"})
        with pytest.raises(ValidationError):
            await user_service.create_user(cmd)


@pytest.mark.django_db(transaction=True)
class TestGetUser:
    async def test_get_user_existing(self, test_user) -> None:
        user = await user_service.get_user(GetUserCmd(user_id=test_user.id))
        assert user is not None
        assert user.id == test_user.id

    async def test_get_user_missing(self) -> None:
        user = await user_service.get_user(GetUserCmd(user_id=999_999))
        assert user is None


@pytest.mark.django_db(transaction=True)
class TestUpdateUser:
    async def test_update_user_partial(self, test_user) -> None:
        cmd = UpdateUserCmd(user_id=test_user.id, first_name="Updated")
        user = await user_service.update_user(cmd)

        assert user is not None
        assert user.first_name == "Updated"

    async def test_update_user_missing(self) -> None:
        cmd = UpdateUserCmd(user_id=999_999, first_name="Updated")
        user = await user_service.update_user(cmd)
        assert user is None

    async def test_update_user_explicit_none_clears_nullable_field(
        self,
        test_user,
    ) -> None:
        test_user.patronymic = "Keep"
        await test_user.asave()

        cmd = UpdateUserCmd(user_id=test_user.id, patronymic=None)
        user = await user_service.update_user(cmd)

        assert user is not None
        assert user.patronymic is None

    async def test_update_user_duplicate_email(self, test_user, user_data) -> None:
        other = await User.objects.acreate_user(
            username="other_user",
            email="other@example.com",
            password="testpass123",
        )
        cmd = UpdateUserCmd(user_id=test_user.id, email=other.email)
        with pytest.raises(ConflictError):
            await user_service.update_user(cmd)


@pytest.mark.django_db(transaction=True)
class TestDeleteUser:
    async def test_delete_user_existing(self, test_user) -> None:
        deleted = await user_service.delete_user(DeleteUserCmd(user_id=test_user.id))
        assert deleted is True
        assert await User.objects.filter(id=test_user.id).aexists() is False

    async def test_delete_user_missing(self) -> None:
        deleted = await user_service.delete_user(DeleteUserCmd(user_id=999_999))
        assert deleted is False
