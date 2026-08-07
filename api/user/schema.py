# api/user/schema.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from ninja import Schema
from pydantic import ConfigDict, Field, field_validator

type UserID = int
type MessageID = int
type PhotoID = int


def _field(description: str, **kwargs: Any) -> Any:
    """Field with metadata via pydantic v2 json_schema_extra."""
    kwargs["json_schema_extra"] = {"metadata": {"description": description}}
    return Field(**kwargs)


class UserOutSchema(Schema):
    """Full user profile."""

    model_config = ConfigDict(from_attributes=True)

    id: UserID = _field("User ID")
    username: str = _field("Unique username")
    email: str = _field("User email")
    first_name: str | None = _field("First name", default=None)
    last_name: str | None = _field("Last name", default=None)
    patronymic: str | None = _field("Patronymic", default=None)
    is_staff: bool = _field("Staff flag", default=False)
    is_active: bool = _field("Active flag", default=True)


class UserCreateIn(Schema):
    """Input for creating a user."""

    username: str = _field(
        "Unique username",
        min_length=3,
        max_length=150,
    )
    email: str = _field("User email")
    password: str = _field(
        "Password (minimum 8 characters)",
        min_length=8,
        max_length=128,
    )
    first_name: str | None = _field("First name", default=None)
    last_name: str | None = _field("Last name", default=None)
    patronymic: str | None = _field("Patronymic", default=None)


class UserUpdateIn(Schema):
    """Input for partial user update."""

    username: str | None = _field(
        "Unique username",
        default=None,
        min_length=3,
        max_length=150,
    )
    email: str | None = _field("User email", default=None)
    first_name: str | None = _field("First name", default=None)
    last_name: str | None = _field("Last name", default=None)
    patronymic: str | None = _field("Patronymic", default=None)
    is_staff: bool | None = _field("Staff flag", default=None)
    is_active: bool | None = _field("Active flag", default=None)


class UserLoginIn(Schema):
    """Input for login."""

    username: str = _field("Username")
    password: str = _field("Password")


class UserTokenOut(Schema):
    """JWT token response."""

    access_token: str = _field("JWT access token")
    token_type: Literal["Bearer"] = "Bearer"


class MessageIn(Schema):
    """Input for creating a message."""

    content: str = _field(
        "Message text",
        min_length=1,
        max_length=4000,
    )


class MessageOut(Schema):
    """Message output."""

    model_config = ConfigDict(from_attributes=True)

    id: MessageID = _field("Message ID")
    content: str = _field("Message text")
    timestamp: datetime = _field("Created at")
    sender: str = _field("Sender username")

    @field_validator("sender", mode="before")
    @classmethod
    def _sender_to_username(cls, value: object) -> object:
        if hasattr(value, "username"):
            return value.username
        return value


class PhotoOut(Schema):
    """User photo output."""

    model_config = ConfigDict(from_attributes=True)

    id: PhotoID = _field("Photo ID")
    image: str = _field("Image URL")
    user_id: UserID = _field("Photo owner")
