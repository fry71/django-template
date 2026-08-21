# api/user/api.py
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import TypedDict

import jwt
from django.conf import settings
from dmr import modify
from dmr.components import (  # DMR resolves these at runtime
    Body,
    FileMetadata,
    Path,
    Query,
)
from dmr.parsers import MultiPartParser
from dmr.plugins.pydantic import PydanticSerializer
from dmr.security.jwt import JWTAsyncAuth
from dmr.security.jwt.views import (
    ObtainTokensAsyncController,
    ObtainTokensPayload,
    ObtainTokensResponse,
    RefreshTokenAsyncController,
    RefreshTokenPayload,
)

from api.common.controllers import (
    ERROR_RESPONSES,
    BaseAsyncController,
    DomainErrorMixin,
)
from api.common.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    UnauthorizedError,
    ValidationError,
)
from api.common.pagination import build_page, paginate
from api.common.schemas import OperationResultSchema
from api.user import schema
from api.user.models import UsedRefreshToken
from api.user.models import User as UserModel
from api.user.services import (
    message_service,
    photo_service,
    room_service,
    user_service,
)

logger = logging.getLogger(__name__)


def _access_lifetime_minutes() -> int:
    """Return the JWT access-token lifetime in minutes (lazy settings read)."""
    return settings.JWT_ACCESS_TOKEN_LIFETIME


# JWTAsyncAuth binds settings at import time; api.user.api must therefore be
# imported only after Django has configured the app registry (see api.web.asgi).
JWT_AUTH = JWTAsyncAuth(
    secret=settings.JWT_SECRET_KEY,
    algorithm=settings.JWT_ALGORITHM,
)


class _UserIdPath(TypedDict):
    """Path parameters for user detail routes."""

    user_id: int


class _MessageIdPath(TypedDict):
    """Path parameters for message detail routes."""

    message_id: int


class _RoomIdPath(TypedDict):
    """Path parameters for room detail routes."""

    room_id: int


class ObtainAccessAndRefreshController(
    ObtainTokensAsyncController[
        PydanticSerializer,
        ObtainTokensPayload,
        ObtainTokensResponse,
    ],
):
    """Issue an access and refresh token pair for valid credentials."""

    jwt_secret = settings.JWT_SECRET_KEY

    async def convert_auth_payload(
        self,
        payload: ObtainTokensPayload,
    ) -> ObtainTokensPayload:
        """Pass the typed login payload through to django authenticate."""
        return payload

    async def make_api_response(self) -> ObtainTokensResponse:
        """Build the access/refresh token pair."""
        now = datetime.now(UTC)
        return {
            "access_token": self.create_jwt_token(
                expiration=now + timedelta(minutes=_access_lifetime_minutes()),
                token_type="access",
            ),
            "refresh_token": self.create_jwt_token(
                expiration=now + self.jwt_refresh_expiration,
                token_type="refresh",
            ),
        }


class RefreshAccessAndRefreshController(
    DomainErrorMixin,
    RefreshTokenAsyncController[
        PydanticSerializer,
        RefreshTokenPayload,
        ObtainTokensResponse,
    ],
):
    """Issue a fresh token pair from a valid refresh token.

    Implements rotation: the presented refresh token's jti is denylisted,
    so each refresh token can be used only once.
    """

    jwt_secret = settings.JWT_SECRET_KEY
    responses = ERROR_RESPONSES

    async def convert_refresh_payload(self, payload: RefreshTokenPayload) -> str:
        """Validate the raw refresh token and denylist its jti."""
        raw_token = payload["refresh_token"]
        claims = jwt.decode(
            raw_token,
            self.jwt_secret,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if claims.get("extras", {}).get("type") != "refresh":
            msg = "Refresh token required"
            raise UnauthorizedError(msg)
        token_jti = claims.get("jti")
        if not token_jti:
            msg = "Refresh token has no jti"
            raise UnauthorizedError(msg)
        if await UsedRefreshToken.objects.filter(jti=token_jti).aexists():
            msg = "Refresh token already used"
            raise UnauthorizedError(msg)
        self._raw_refresh_claims = claims
        return raw_token

    async def make_api_response(self) -> ObtainTokensResponse:
        """Build the refreshed pair and record the rotated jti."""
        now = datetime.now(UTC)
        response: ObtainTokensResponse = {
            "access_token": self.create_jwt_token(
                expiration=now + timedelta(minutes=_access_lifetime_minutes()),
                token_type="access",
            ),
            "refresh_token": self.create_jwt_token(
                expiration=now + self.jwt_refresh_expiration,
                token_type="refresh",
            ),
        }
        await self._denylist_used_refresh()
        return response

    async def _denylist_used_refresh(self) -> None:
        """Store the presented refresh token's jti until it expires."""
        claims = getattr(self, "_raw_refresh_claims", None)
        if not claims:
            return
        try:
            await UsedRefreshToken.objects.acreate(
                jti=claims["jti"],
                expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
            )
        except Exception:
            logger.exception("Failed to denylist rotated refresh token")


def _current_user(controller: BaseAsyncController) -> UserModel:
    """Return the authenticated user, narrowing the request user type."""
    user = controller.request.user
    if not isinstance(user, UserModel):
        msg = "Expected an authenticated user"
        raise UnauthorizedError(msg)
    return user


def _current_user_id(controller: BaseAsyncController) -> int:
    """Return the authenticated user's id."""
    return _current_user(controller).pk


async def _existing_user(user_id: int) -> UserModel:
    """Return the user by id or raise NotFoundError."""
    user = await user_service.get_user(user_id)
    if user is None:
        msg = "User not found"
        raise NotFoundError(msg)
    return user


class UserListController(BaseAsyncController):
    """List users (paginated) or create a new one."""

    @modify(auth=(JWT_AUTH,))
    async def get(self, parsed_query: Query[schema.PageQuery]) -> schema.UsersPage:
        """Paginated user list."""
        records, info = await paginate(
            user_service.user_queryset(),
            parsed_query.page,
            parsed_query.page_size,
        )
        users = [
            schema.UserOutSchema.model_validate(user, from_attributes=True)
            for user in records
        ]
        return build_page(
            schema.UsersPage,
            users,
            info,
            parsed_query.page,
            parsed_query.page_size,
        )

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[schema.UserCreateIn]) -> schema.UserOutSchema:
        """Create a new user."""
        user = await user_service.create_user(parsed_body)
        return schema.UserOutSchema.model_validate(user, from_attributes=True)


class UserDetailController(BaseAsyncController):
    """Read, update, or delete a single user."""

    auth = (JWT_AUTH,)

    async def get(self, parsed_path: Path[_UserIdPath]) -> schema.UserOutSchema:
        """Get a user by id."""
        user = await _existing_user(parsed_path["user_id"])
        return schema.UserOutSchema.model_validate(user, from_attributes=True)

    async def put(
        self,
        parsed_path: Path[_UserIdPath],
        parsed_body: Body[schema.UserUpdateIn],
    ) -> schema.UserOutSchema:
        """Update a user partially."""
        user_id = parsed_path["user_id"]
        auth_user = _current_user(self)
        if auth_user.id != user_id and not auth_user.is_staff:
            msg = "No permission to edit"
            raise PermissionDeniedError(msg)

        user = await user_service.update_user(user_id, parsed_body)
        if user is None:
            msg = "User not found"
            raise NotFoundError(msg)
        return schema.UserOutSchema.model_validate(user, from_attributes=True)

    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def delete(self, parsed_path: Path[_UserIdPath]) -> None:
        """Delete a user."""
        user_id = parsed_path["user_id"]
        auth_user = _current_user(self)
        if auth_user.id != user_id and not auth_user.is_staff:
            msg = "No permission to delete"
            raise PermissionDeniedError(msg)

        deleted = await user_service.delete_user(user_id)
        if not deleted:
            msg = "User not found"
            raise NotFoundError(msg)


class MeController(BaseAsyncController):
    """Return the currently authenticated user."""

    auth = (JWT_AUTH,)

    async def get(self) -> schema.UserOutSchema:
        """Return the current authenticated user."""
        return schema.UserOutSchema.model_validate(
            _current_user(self), from_attributes=True
        )


class MessageListController(BaseAsyncController):
    """List messages (paginated, searchable) or create a new one."""

    auth = (JWT_AUTH,)

    async def get(
        self,
        parsed_query: Query[schema.MessagePageQuery],
    ) -> schema.MessagesPage:
        """Paginated message list with optional search."""
        records, info = await paginate(
            message_service.message_queryset(
                room_id=parsed_query.room_id,
                search=parsed_query.search,
                sort=parsed_query.sort,
            ),
            parsed_query.page,
            parsed_query.page_size,
        )
        messages = [
            schema.MessageOut.model_validate(message, from_attributes=True)
            for message in records
        ]
        return build_page(
            schema.MessagesPage,
            messages,
            info,
            parsed_query.page,
            parsed_query.page_size,
        )

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[schema.MessageIn]) -> schema.MessageOut:
        """Create a message in a chat room."""
        user = _current_user(self)
        if not await room_service.is_member(parsed_body.room_id, user.id):
            msg = "Not a member of this room"
            raise PermissionDeniedError(msg)
        message = await message_service.create_message(
            sender_id=user.id,
            room_id=parsed_body.room_id,
            message_content=parsed_body.content,
        )
        message.sender = user
        return schema.MessageOut.model_validate(message, from_attributes=True)


class MessageDetailController(BaseAsyncController):
    """Delete a single message."""

    auth = (JWT_AUTH,)

    async def delete(
        self,
        parsed_path: Path[_MessageIdPath],
    ) -> OperationResultSchema:
        """Delete a message owned by the current user."""
        message_id = parsed_path["message_id"]
        message = await message_service.get_message(message_id)
        if message is None:
            msg = "Message not found"
            raise NotFoundError(msg)
        auth_user = _current_user(self)
        if message.sender_id != auth_user.id and not auth_user.is_staff:
            msg = "No permission to delete message"
            raise PermissionDeniedError(msg)

        await message_service.delete_message(message_id)
        return OperationResultSchema(detail="Message deleted")


class RoomListController(BaseAsyncController):
    """List the current user's rooms or create a new room."""

    auth = (JWT_AUTH,)

    async def get(self, parsed_query: Query[schema.PageQuery]) -> schema.RoomsPage:
        """Paginated list of rooms the current user belongs to."""
        user = _current_user(self)
        records, info = await paginate(
            room_service.room_queryset().filter(members=user),
            parsed_query.page,
            parsed_query.page_size,
        )
        rooms = [
            schema.RoomOut.model_validate(room, from_attributes=True) for room in records
        ]
        return build_page(
            schema.RoomsPage,
            rooms,
            info,
            parsed_query.page,
            parsed_query.page_size,
        )

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[schema.RoomCreateIn]) -> schema.RoomOut:
        """Create a group chat room."""
        room = await room_service.create_room(_current_user_id(self), parsed_body)
        return schema.RoomOut.model_validate(room, from_attributes=True)


class DirectRoomController(BaseAsyncController):
    """Create or fetch a 1:1 direct room with another user."""

    auth = (JWT_AUTH,)

    @modify(status_code=HTTPStatus.CREATED)
    async def post(
        self,
        parsed_body: Body[schema.DirectRoomCreateIn],
    ) -> schema.RoomOut:
        """Return the existing direct room or create a new one."""
        user = _current_user(self)
        if parsed_body.peer_id == user.id:
            msg = "Cannot create a direct room with yourself"
            raise ValidationError(msg)
        await _existing_user(parsed_body.peer_id)
        room = await room_service.get_or_create_direct_room(
            user_a_id=user.id,
            user_b_id=parsed_body.peer_id,
        )
        return schema.RoomOut.model_validate(room, from_attributes=True)


class RoomMembershipController(BaseAsyncController):
    """Join or leave a chat room."""

    auth = (JWT_AUTH,)

    @modify()
    async def post(
        self,
        parsed_path: Path[_RoomIdPath],
    ) -> OperationResultSchema:
        """Join a public room."""
        joined = await room_service.join_room(
            parsed_path["room_id"],
            _current_user_id(self),
        )
        if not joined:
            msg = "Room not found"
            raise NotFoundError(msg)
        return OperationResultSchema(detail="Joined the room")

    @modify()
    async def delete(
        self,
        parsed_path: Path[_RoomIdPath],
    ) -> OperationResultSchema:
        """Leave a room."""
        left = await room_service.leave_room(
            parsed_path["room_id"],
            _current_user_id(self),
        )
        if not left:
            msg = "Room not found"
            raise NotFoundError(msg)
        return OperationResultSchema(detail="Left the room")


class PhotoListController(BaseAsyncController):
    """List the current user's photos or upload a new one."""

    auth = (JWT_AUTH,)
    parsers = (MultiPartParser(),)

    async def get(self, parsed_query: Query[schema.PageQuery]) -> schema.PhotosPage:
        """List photos for the current user."""
        records, info = await paginate(
            photo_service.photo_queryset(_current_user_id(self)),
            parsed_query.page,
            parsed_query.page_size,
        )
        photos = [
            schema.PhotoOut.model_validate(photo, from_attributes=True)
            for photo in records
        ]
        return build_page(
            schema.PhotosPage,
            photos,
            info,
            parsed_query.page,
            parsed_query.page_size,
        )

    @modify(status_code=HTTPStatus.CREATED)
    async def post(
        self,
        parsed_file_metadata: FileMetadata[
            schema.PhotosUpload
        ],  # DMR passes it by contract
    ) -> schema.PhotoOut:
        """Upload a photo for the current user."""
        uploaded = self.request.FILES.get("image")
        if uploaded is None:
            msg = "No image file provided"
            raise NotFoundError(msg)
        photo = await photo_service.create_photo(_current_user_id(self), uploaded)
        return schema.PhotoOut.model_validate(photo, from_attributes=True)
