# api/user/api.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import TypedDict

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

from api.common.controllers import BaseAsyncController
from api.common.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    UnauthorizedError,
)
from api.common.pagination import build_page, paginate
from api.common.schemas import OperationResultSchema
from api.user import schema
from api.user.models import User
from api.user.services import message_service, photo_service, user_service


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
    RefreshTokenAsyncController[
        PydanticSerializer,
        RefreshTokenPayload,
        ObtainTokensResponse,
    ],
):
    """Issue a fresh token pair from a valid refresh token."""

    jwt_secret = settings.JWT_SECRET_KEY

    async def convert_refresh_payload(self, payload: RefreshTokenPayload) -> str:
        """Extract the raw refresh token string from the payload."""
        return payload["refresh_token"]

    async def make_api_response(self) -> ObtainTokensResponse:
        """Build the refreshed access/refresh token pair."""
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


def _current_user(controller: BaseAsyncController) -> User:
    """Return the authenticated user, narrowing the request user type."""
    user = controller.request.user
    if not isinstance(user, User):
        msg = "Expected an authenticated user"
        raise UnauthorizedError(msg)
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
        user = await user_service.get_user(parsed_path["user_id"])
        if user is None:
            msg = "User not found"
            raise NotFoundError(msg)
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
        """Create a message."""
        user = _current_user(self)
        message = await message_service.create_message(
            user.id,
            parsed_body.content,
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


class PhotoListController(BaseAsyncController):
    """List the current user's photos or upload a new one."""

    auth = (JWT_AUTH,)
    parsers = (MultiPartParser(),)

    async def get(self, parsed_query: Query[schema.PageQuery]) -> schema.PhotosPage:
        """List photos for the current user."""
        records, info = await paginate(
            photo_service.photo_queryset(_current_user(self).id),
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
        photo = await photo_service.create_photo(_current_user(self).id, uploaded)
        return schema.PhotoOut.model_validate(photo, from_attributes=True)
