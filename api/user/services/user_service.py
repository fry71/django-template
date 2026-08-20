# api/user/services/user_service.py
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from django.contrib.auth import aauthenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from api.common.exceptions import ConflictError, ValidationError
from api.user.tasks import send_welcome_email

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from api.user.schema import UserCreateIn, UserUpdateIn

logger = logging.getLogger(__name__)

User = get_user_model()

_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


async def get_user(user_id: int) -> User | None:
    """Return user by id or None."""
    try:
        return await User.objects.aget(id=user_id)
    except User.DoesNotExist:
        return None


def user_queryset() -> QuerySet[User]:
    """Return base queryset with default ordering."""
    return User.objects.all().order_by("-id")


async def _validate_unique_email(user_id: int | None, email: str) -> None:
    """Validate email format and uniqueness for a user."""
    if not _EMAIL_PATTERN.match(email):
        msg = "Invalid email format"
        raise ValidationError(msg, fields={"email": [msg]})

    queryset = User.objects.all()
    if user_id is not None:
        queryset = queryset.exclude(id=user_id)
    if await queryset.filter(email=email).afirst():
        msg = "Email already exists"
        raise ConflictError(msg, fields={"email": [msg]})


async def create_user(payload: UserCreateIn) -> User:
    """Create a user.

    Simple write (single INSERT) — use acreate() without a transaction bridge.
    Background tasks (e.g. welcome email) are dispatched via kiq AFTER commit.
    """
    await _validate_unique_email(None, payload.email)

    try:
        validate_password(payload.password)
    except DjangoValidationError as exc:
        messages = list(exc.messages)
        raise ValidationError("; ".join(messages), fields={"password": messages}) from exc

    user = await User.objects.acreate_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        first_name=payload.first_name,
        last_name=payload.last_name,
        patronymic=payload.patronymic,
    )
    logger.info("User created: %s", user.username)

    try:
        await send_welcome_email.kiq(user.id)
    except Exception:
        logger.exception("Failed to enqueue welcome email for user %s", user.id)

    return user


async def update_user(user_id: int, payload: UserUpdateIn) -> User | None:
    """Update a user.

    Single-model read-modify-write — simple write via asave().
    Returns None if the user is not found.
    """
    user = await get_user(user_id)
    if user is None:
        return None

    update_data = payload.model_dump(exclude_unset=True)

    email = update_data.get("email")
    if email:
        await _validate_unique_email(user_id, email)

    for key, field_value in update_data.items():
        setattr(user, key, field_value)
    await user.asave()
    logger.info("User updated: %s", user.username)
    return user


async def delete_user(user_id: int) -> bool:
    """Delete a user. Returns True/False."""
    user = await get_user(user_id)
    if user is None:
        return False

    await user.adelete()
    logger.info("User deleted: %s", user_id)
    return True


async def authenticate(username: str, password: str) -> User | None:
    """Authenticate a user."""
    return await aauthenticate(username=username, password=password)
