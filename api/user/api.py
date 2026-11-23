# api/user/api.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING, TypedDict, cast

from django.conf import settings
from django.db import IntegrityError
from dmr import modify
from dmr.components import (  # DMR resolves these at runtime
    Body,
    FileMetadata,
    Path,
    Query,
)
from dmr.exceptions import NotAuthenticatedError
from dmr.pagination import CursorPaginated, CursorPaginator
from dmr.parsers import MultiPartParser
from dmr.plugins.pydantic import PydanticFastSerializer, PydanticSerializer
from dmr.security.base import NO_STORE_HEADERS
from dmr.security.jwt import HeaderJWTAsyncAuth
from dmr.security.jwt.views import (
    ObtainTokensAsyncController,
    ObtainTokensPayload,
    ObtainTokensResponse,
    RefreshTokenAsyncController,
    RefreshTokenPayload,
)
from dmr.throttling import AsyncThrottle

from api.common import lockout
from api.common.controllers import (
    AUTHENTICATION_REQUIRED,
    BaseAsyncController,
    DomainErrorMixin,
)
from api.common.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
)
from api.common.pagination import build_page, paginate
from api.common.throttling import UsernameFromBody
from api.user import mappers, schema
from api.user.models import UsedRefreshToken
from api.user.models import User as UserModel
from api.user.services import (
    cmds,
    message_service,
    photo_service,
    room_service,
    user_service,
)

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile
    from dmr import Controller

# RFC 9110 (15.5.2) requires a challenge on every 401. dmr adds it on its own
# for every endpoint with an auth chain (``add_www_authenticate`` in
# ``global_error_handler``); the token endpoints below authenticate with a
# body and have no auth chain, so they supply the challenge manually and
# declare it in their response specs (``AUTHENTICATION_REQUIRED``).


def _auth_challenge() -> dict[str, str]:
    """Return the challenge sent with every 401 of the token endpoints."""
    return {"WWW-Authenticate": "Bearer"}


# Brute-force protection on auth endpoints (dmr docs: never have auth
# without throttling before it).
# Per-client burst guard, keyed by the address the request came from:
_AUTH_THROTTLE = AsyncThrottle(max_requests=10, duration_in_seconds=60)
# Per-account guard: an attacker spraying a single username from many
# addresses is limited here, while api.common.lockout counts the failures
# and keeps the account locked for a cooloff window.
LOGIN_ATTEMPTS_PER_MINUTE = 10
_LOGIN_THROTTLE = AsyncThrottle(
    max_requests=LOGIN_ATTEMPTS_PER_MINUTE,
    duration_in_seconds=60,
    cache_key=UsernameFromBody(),
)


def _access_lifetime_minutes() -> int:
    """Return the JWT access-token lifetime in minutes (lazy settings read)."""
    return settings.JWT_ACCESS_TOKEN_LIFETIME


# HeaderJWTAsyncAuth binds settings at import time; api.user.api must
# therefore be imported only after Django has configured the app registry
# (see api.web.asgi).
JWT_AUTH = HeaderJWTAsyncAuth(
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
    DomainErrorMixin,
    ObtainTokensAsyncController[
        PydanticFastSerializer,
        ObtainTokensPayload,
        ObtainTokensResponse,
    ],
):
    """Issue an access and refresh token pair for valid credentials.

    Failed attempts are counted per account in ``api.common.lockout``: after
    ``LOGIN_MAX_FAILED_ATTEMPTS`` the account is locked for
    ``LOGIN_LOCKOUT_SECONDS`` and answers 429 even for correct credentials.
    """

    jwt_secret = settings.JWT_SECRET_KEY
    throttling = (_AUTH_THROTTLE, _LOGIN_THROTTLE)

    @classmethod
    def modify_spec(cls) -> object:
        """Declare the 401 challenge that dmr's own token spec leaves out."""
        return modify(
            status_code=cls.response_status_code,
            extra_responses=[AUTHENTICATION_REQUIRED],
            headers=NO_STORE_HEADERS,
        )

    async def convert_auth_payload(
        self,
        payload: ObtainTokensPayload,
    ) -> ObtainTokensPayload:
        """Pass the typed login payload through to django authenticate."""
        return payload

    async def login(self, parsed_body: ObtainTokensPayload) -> ObtainTokensResponse:
        """Authenticate the user, tracking failed attempts for lockout."""
        username = parsed_body["username"]
        state = await lockout.check(username)
        if state.locked:
            msg = "Too many failed login attempts, try again later"
            raise RateLimitError(
                msg,
                retry_after=state.retry_after,
                limit=lockout.MAX_FAILED_LOGINS,
            )
        try:
            response = await super().login(parsed_body)
        except NotAuthenticatedError as exc:
            await lockout.register_failure(username)
            # dmr's login flow builds a bare 401; add the RFC 9110 challenge
            # without dropping any headers dmr may have set itself.
            if exc.headers is None:
                exc.headers = _auth_challenge()
            raise
        await lockout.reset(username)
        return response

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
        PydanticFastSerializer,
        RefreshTokenPayload,
        ObtainTokensResponse,
    ],
):
    """Issue a fresh token pair from a valid refresh token.

    Implements rotation: the presented refresh token's jti is denylisted
    before the new pair is issued, so each refresh token works only once.

    The contract is exactly what this endpoint can answer — 200, 400 for
    a malformed body, 401 with the RFC 9110 challenge, and the semantic
    406/422/429 — unlike ``ERROR_RESPONSES`` of the domain controllers,
    which is why ``responses`` is not overridden here.
    """

    jwt_secret = settings.JWT_SECRET_KEY

    @classmethod
    def modify_spec(cls) -> object:
        """Declare the 401 challenge that dmr's own token spec leaves out."""
        return modify(
            status_code=cls.response_status_code,
            extra_responses=[AUTHENTICATION_REQUIRED],
            headers=NO_STORE_HEADERS,
        )

    throttling = (_AUTH_THROTTLE,)

    async def convert_refresh_payload(self, payload: RefreshTokenPayload) -> str:
        """Validate the token's claims and burn its jti (rotation).

        ``JWT_AUTH.decode_token`` turns any bad token — bad signature,
        expired, malformed — into the same ``NotAuthenticatedError`` the
        parent ``refresh()`` flow raises, so no pyjwt error ever escapes
        as a 500. The unique ``jti`` column is the single point of truth:
        two concurrent refreshes of the same token race on this INSERT
        and exactly one of them wins. Token type and user existence are
        validated by the parent flow afterwards.
        """
        raw_token = payload["refresh_token"]
        try:
            token = JWT_AUTH.decode_token(raw_token)
        except NotAuthenticatedError as exc:
            # The endpoint has no auth chain, so the RFC 9110 challenge
            # is not added automatically here.
            if exc.headers is None:
                exc.headers = _auth_challenge()
            raise
        if not token.jti:
            msg = "Refresh token has no jti claim"
            raise NotAuthenticatedError(msg, headers=_auth_challenge())
        try:
            await UsedRefreshToken.objects.acreate(
                jti=token.jti,
                expires_at=token.exp,
            )
        except IntegrityError as exc:
            msg = "Refresh token already used"
            raise NotAuthenticatedError(msg, headers=_auth_challenge()) from exc
        return raw_token

    async def make_api_response(self) -> ObtainTokensResponse:
        """Build the refreshed pair; the used jti is already denylisted."""
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


def _current_user(controller: Controller[PydanticSerializer]) -> UserModel:
    """Return the authenticated user, narrowing the request user type.

    dmr's error handler adds the ``WWW-Authenticate`` challenge itself:
    every endpoint calling this has a JWT auth in its chain.
    """
    user = controller.request.user
    if not isinstance(user, UserModel):
        msg = "Expected an authenticated user"
        raise NotAuthenticatedError(msg)
    return user


def _current_user_id(controller: Controller[PydanticSerializer]) -> int:
    """Return the authenticated user's id."""
    return _current_user(controller).pk


async def _existing_user(user_id: int) -> UserModel:
    """Return the user by id or raise NotFoundError."""
    user = await user_service.get_user(cmds.GetUserCmd(user_id=user_id))
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
        users = [mappers.user_out(user) for user in records]
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
        user = await user_service.create_user(mappers.create_user_cmd(parsed_body))
        return mappers.user_out(user)


class UserDetailController(BaseAsyncController):
    """Read, update, or delete a single user."""

    auth = (JWT_AUTH,)

    async def get(self, parsed_path: Path[_UserIdPath]) -> schema.UserOutSchema:
        """Get a user by id."""
        user = await _existing_user(parsed_path["user_id"])
        return mappers.user_out(user)

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

        user = await user_service.update_user(
            mappers.update_user_cmd(user_id, parsed_body),
        )
        if user is None:
            msg = "User not found"
            raise NotFoundError(msg)
        return mappers.user_out(user)

    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def delete(self, parsed_path: Path[_UserIdPath]) -> None:
        """Delete a user."""
        user_id = parsed_path["user_id"]
        auth_user = _current_user(self)
        if auth_user.id != user_id and not auth_user.is_staff:
            msg = "No permission to delete"
            raise PermissionDeniedError(msg)

        deleted = await user_service.delete_user(cmds.DeleteUserCmd(user_id=user_id))
        if not deleted:
            msg = "User not found"
            raise NotFoundError(msg)


class MeController(BaseAsyncController):
    """Return the currently authenticated user."""

    auth = (JWT_AUTH,)

    async def get(self) -> schema.UserOutSchema:
        """Return the current authenticated user."""
        return mappers.user_out(_current_user(self))


class MessageListController(BaseAsyncController):
    """List messages (paginated, searchable) or create a new one."""

    auth = (JWT_AUTH,)

    async def get(
        self,
        parsed_query: Query[schema.MessageCursorQuery],
    ) -> CursorPaginated[schema.MessageOut]:
        """Cursor-paginated message list with optional search.

        The feed keeps receiving new rows, so page numbers would skip
        or duplicate messages between requests; the cursor is the
        position of the last seen row instead. It is bound to the
        ordering and filters it was created with — do not change
        ``sort``/``room_id``/``search`` while following one.
        """
        paginator = CursorPaginator(
            message_service.message_queryset(
                mappers.list_messages_query(parsed_query),
            ),
            per_page=parsed_query.limit,
        )
        page = await paginator.apage(parsed_query.cursor)
        return CursorPaginated(
            next_cursor=page.next_cursor,
            per_page=paginator.per_page,
            page=[mappers.message_out(message) for message in page.objects_list],
        )

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[schema.MessageIn]) -> schema.MessageOut:
        """Create a message in a chat room."""
        user = _current_user(self)
        if not await room_service.is_member(
            cmds.IsRoomMemberQuery(room_id=parsed_body.room_id, user_id=user.id),
        ):
            msg = "Not a member of this room"
            raise PermissionDeniedError(msg)
        message = await message_service.create_message(
            mappers.create_message_cmd(parsed_body, sender_id=user.id),
        )
        message.sender = user
        return mappers.message_out(message)


class MessageDetailController(BaseAsyncController):
    """Delete a single message."""

    auth = (JWT_AUTH,)

    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def delete(
        self,
        parsed_path: Path[_MessageIdPath],
    ) -> None:
        """Delete a message owned by the current user."""
        message_id = parsed_path["message_id"]
        message = await message_service.get_message(
            cmds.GetMessageCmd(message_id=message_id),
        )
        if message is None:
            msg = "Message not found"
            raise NotFoundError(msg)
        auth_user = _current_user(self)
        if message.sender_id != auth_user.id and not auth_user.is_staff:
            msg = "No permission to delete message"
            raise PermissionDeniedError(msg)

        await message_service.delete_message(
            cmds.DeleteMessageCmd(message_id=message_id),
        )


class RoomListController(BaseAsyncController):
    """List the current user's rooms or create a new room."""

    auth = (JWT_AUTH,)

    async def get(self, parsed_query: Query[schema.PageQuery]) -> schema.RoomsPage:
        """Paginated list of rooms the current user belongs to."""
        user = _current_user(self)
        records, info = await paginate(
            room_service.rooms_for_user(cmds.ListRoomsQuery(user_id=user.id)),
            parsed_query.page,
            parsed_query.page_size,
        )
        rooms = [mappers.room_out(room) for room in records]
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
        room = await room_service.create_room(
            mappers.create_room_cmd(parsed_body, creator_id=_current_user_id(self)),
        )
        return mappers.room_out(room)


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
            cmds.EnsureDirectRoomCmd(user_a_id=user.id, user_b_id=parsed_body.peer_id),
        )
        return mappers.room_out(room)


class RoomMembershipController(BaseAsyncController):
    """Join or leave a chat room."""

    auth = (JWT_AUTH,)

    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def post(
        self,
        parsed_path: Path[_RoomIdPath],
    ) -> None:
        """Join a public room."""
        joined = await room_service.join_room(
            cmds.JoinRoomCmd(
                room_id=parsed_path["room_id"],
                user_id=_current_user_id(self),
            ),
        )
        if not joined:
            msg = "Room not found"
            raise NotFoundError(msg)

    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def delete(
        self,
        parsed_path: Path[_RoomIdPath],
    ) -> None:
        """Leave a room."""
        left = await room_service.leave_room(
            cmds.LeaveRoomCmd(
                room_id=parsed_path["room_id"],
                user_id=_current_user_id(self),
            ),
        )
        if not left:
            msg = "Room not found"
            raise NotFoundError(msg)


class PhotoListController(BaseAsyncController[PydanticSerializer]):
    """List the current user's photos or upload a new one.

    ``PydanticSerializer`` instead of the ``PydanticFastSerializer``
    default: this controller parses ``multipart/form-data``.
    """

    auth = (JWT_AUTH,)
    parsers = (MultiPartParser(),)

    async def get(self, parsed_query: Query[schema.PageQuery]) -> schema.PhotosPage:
        """List photos for the current user."""
        records, info = await paginate(
            photo_service.photo_queryset(
                cmds.ListPhotosQuery(user_id=_current_user_id(self)),
            ),
            parsed_query.page,
            parsed_query.page_size,
        )
        photos = [mappers.photo_out(photo) for photo in records]
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
        """Upload a photo for the current user.

        The file itself is handled by Django (``request.FILES``); the
        ``parsed_file_metadata`` component validated its MIME type and size,
        so the endpoint and the service can trust the upload.
        """
        photo = await photo_service.create_photo(
            cmds.UploadPhotoCmd(
                user_id=_current_user_id(self),
                # DMR validates the metadata; Django owns the file itself.
                uploaded=cast("UploadedFile", self.request.FILES["image"]),
            ),
        )
        return mappers.photo_out(photo)
