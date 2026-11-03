# api/user/services/cmds.py
"""Command and query DTOs — the service layer contract.

Pydantic models stay at the boundary (``api/user/schema.py``): controllers
validate the request, map it to one of these immutable dataclasses, call the
service, and map the domain object back to a response schema.

Services accept these dataclasses only — never Pydantic schemas, raw dicts,
or ``**kwargs`` bags.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile


class _Unset:
    """Sentinel type for a command field the caller did not provide."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET = _Unset()
type Unset = _Unset


# --- users ---------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateUserCmd:
    """Register a new user account."""

    username: str
    email: str
    password: str
    first_name: str | None = None
    last_name: str | None = None
    patronymic: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateUserCmd:
    """Partially update a user; fields left at ``UNSET`` are not touched.

    ``UNSET`` means "not provided" and leaves the field untouched; for a
    nullable column an explicit ``None`` clears it.
    """

    user_id: int
    # NOT NULL columns -> ``None`` is not a valid value.
    username: str | Unset = UNSET
    email: str | Unset = UNSET
    first_name: str | Unset = UNSET
    last_name: str | Unset = UNSET
    is_staff: bool | Unset = UNSET
    is_active: bool | Unset = UNSET
    # Nullable column -> an explicit ``None`` clears it.
    patronymic: str | Unset | None = UNSET

    def provided(self) -> dict[str, object]:
        """Return only the fields the caller explicitly provided."""
        return {
            field.name: getattr(self, field.name)
            for field in fields(self)
            if field.name != "user_id" and getattr(self, field.name) is not UNSET
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class GetUserCmd:
    """Look up a single user by id."""

    user_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DeleteUserCmd:
    """Delete a user by id."""

    user_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthenticateUserCmd:
    """Check username/password credentials."""

    username: str
    password: str


# --- rooms ---------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateRoomCmd:
    """Create a group room owned by ``creator_id``."""

    name: str
    creator_id: int
    is_private: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class GetRoomCmd:
    """Look up a single room by id."""

    room_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class EnsureDirectRoomCmd:
    """Return the 1:1 room between two users, creating it if needed."""

    user_a_id: int
    user_b_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class JoinRoomCmd:
    """Add a user to a public room."""

    room_id: int
    user_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class LeaveRoomCmd:
    """Remove a user from a room."""

    room_id: int
    user_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class IsRoomMemberQuery:
    """Check whether a user belongs to a room."""

    room_id: int
    user_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ListRoomsQuery:
    """List the rooms a user belongs to."""

    user_id: int


# --- messages ------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateMessageCmd:
    """Post a message into a room on behalf of ``sender_id``."""

    sender_id: int
    room_id: int
    content: str


@dataclass(frozen=True, slots=True, kw_only=True)
class GetMessageCmd:
    """Look up a single message by id."""

    message_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DeleteMessageCmd:
    """Delete a message by id."""

    message_id: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ListMessagesQuery:
    """Filters for a paginated message list."""

    room_id: int | None = None
    search: str | None = None
    sort: Literal["asc", "desc"] | None = None


# --- photos --------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class UploadPhotoCmd:
    """Store an uploaded photo for a user.

    ``uploaded`` is a framework file object: file handles cross the service
    boundary as-is, while all scalar input is typed here.
    """

    user_id: int
    uploaded: UploadedFile


@dataclass(frozen=True, slots=True, kw_only=True)
class ListPhotosQuery:
    """List the photos of a user."""

    user_id: int
