# api/user/schema.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypedDict

from dmr.pagination import Paginated
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.user.limits import ALLOWED_IMAGE_PREFIX, MAX_PHOTO_SIZE_BYTES

type UserID = int
type MessageID = int
type PhotoID = int
type RoomID = int


def _field(description: str, **kwargs: Any) -> Any:
    """Field with metadata via pydantic v2 json_schema_extra."""
    kwargs["json_schema_extra"] = {"metadata": {"description": description}}
    return Field(**kwargs)


class UserOutSchema(BaseModel):
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


class UserCreateIn(BaseModel):
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


_NOT_NULLABLE_UPDATE_FIELDS = (
    "username",
    "email",
    "first_name",
    "last_name",
    "is_staff",
    "is_active",
)


class UserUpdateIn(BaseModel):
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

    @field_validator(*_NOT_NULLABLE_UPDATE_FIELDS)
    @classmethod
    def _reject_explicit_null(cls, raw_value: object) -> object:
        """Reject an explicit ``null`` for a NOT NULL column.

        Omitting the field means "leave it as is"; sending ``null`` used to
        reach the database and fail with an IntegrityError. Only nullable
        columns (``patronymic``) accept an explicit ``null`` to clear them.
        """
        if raw_value is None:
            msg = "null is not allowed for this field; omit it instead"
            raise ValueError(msg)
        return raw_value


class MessageIn(BaseModel):
    """Input for creating a message."""

    room_id: RoomID = _field("Target chat room ID")
    content: str = _field(
        "Message text",
        min_length=1,
        max_length=4000,
    )


class MessageOut(BaseModel):
    """Message output."""

    model_config = ConfigDict(from_attributes=True)

    id: MessageID = _field("Message ID")
    content: str = _field("Message text")
    timestamp: datetime = _field("Created at")
    sender: str = _field("Sender username")

    @field_validator("sender", mode="before")
    @classmethod
    def _sender_to_username(cls, raw_value: object) -> object:
        if hasattr(raw_value, "username"):
            return raw_value.username
        return raw_value


class PhotoOut(BaseModel):
    """User photo output."""

    model_config = ConfigDict(from_attributes=True)

    id: PhotoID = _field("Photo ID")
    image: str = _field("Image URL")
    user_id: UserID = _field("Photo owner")

    @field_validator("image", mode="before")
    @classmethod
    def _image_to_url(cls, raw_value: object) -> object:
        if hasattr(raw_value, "url"):
            return raw_value.url
        return raw_value


class PageQuery(BaseModel):
    """Query parameters for paginated collections."""

    page: int = _field("Page number, starting from 1", default=1, ge=1)
    page_size: int = _field("Items per page", default=10, ge=1, le=100)


class MessagePageQuery(PageQuery):
    """Query parameters for the message list."""

    room_id: RoomID | None = _field("Filter by chat room", default=None)
    search: str | None = _field("Full-text search", default=None)
    sort: Literal["asc", "desc"] = _field("Sort order", default="desc")


class RoomCreateIn(BaseModel):
    """Input for creating a group chat room."""

    name: str = _field(
        "Room name",
        min_length=1,
        max_length=255,
    )
    is_private: bool = _field("Private room flag", default=False)


class DirectRoomCreateIn(BaseModel):
    """Input for creating (or fetching) a 1:1 room."""

    peer_id: UserID = _field("The other user ID")


class RoomOut(BaseModel):
    """Chat room output."""

    model_config = ConfigDict(from_attributes=True)

    id: RoomID = _field("Room ID")
    name: str = _field("Room name")
    room_type: Literal["group", "direct"] = _field("Room type")
    is_private: bool = _field("Private room flag")
    created_by_id: UserID = _field("Creator user ID")
    created_at: datetime = _field("Created at")
    updated_at: datetime = _field("Last activity at")


class RoomsPage(Paginated[RoomOut]):
    """Paginated room list."""


class PhotoUploadMeta(BaseModel):
    """Metadata for a single uploaded photo.

    Validated by the ``FileMetadata`` component before the endpoint runs,
    so a wrong type or oversized file is rejected at the boundary.
    """

    name: str = _field("File name")
    content_type: str = _field("MIME type", pattern=f"^{ALLOWED_IMAGE_PREFIX}")
    size: int = _field(
        "File size in bytes",
        le=MAX_PHOTO_SIZE_BYTES,
    )


class PhotosUpload(TypedDict):
    """Metadata for the multipart photo upload."""

    image: PhotoUploadMeta


class UsersPage(Paginated[UserOutSchema]):
    """Paginated user list."""


class MessagesPage(Paginated[MessageOut]):
    """Paginated message list."""


class PhotosPage(Paginated[PhotoOut]):
    """Paginated photo list."""
