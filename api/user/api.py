# api/user/api.py
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt
from django.conf import settings
from ninja import File, Router, UploadedFile
from ninja.pagination import PageNumberPagination, paginate
from ninja.security import HttpBearer

from api.common.exceptions import (
    NotFoundError,
    PermissionDeniedError,
)
from api.common.schemas import ErrorSchema, OperationResultSchema
from api.user.schema import (
    MessageIn,
    MessageOut,
    PhotoOut,
    UserCreateIn,
    UserLoginIn,
    UserOutSchema,
    UserTokenOut,
    UserUpdateIn,
)
from api.user.services import message_service, photo_service, user_service

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

    from api.user.models import Message, Photo, User

logger = logging.getLogger(__name__)

router = Router()


class JWTAuth(HttpBearer):
    """JWT authentication via HttpBearer."""

    async def authenticate(self, request: HttpRequest, token: str) -> User | None:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except jwt.InvalidTokenError as exc:
            logger.warning("JWT invalid: %s", exc)
            return None
        except Exception:
            logger.exception("JWT authenticate unexpected error")
            return None

        user_id = payload.get("user_id")
        if not user_id:
            logger.warning("JWT missing user_id: %s", payload)
            return None
        user = await user_service.get_user(user_id)
        if user is None:
            logger.warning("JWT user %s not found", user_id)
            return None
        request.user = user
        return user


@router.post("/token", response={200: UserTokenOut, 401: ErrorSchema})
async def get_token(
    request: HttpRequest,
    payload: UserLoginIn,
) -> tuple[int, dict[str, str]]:
    """Issue a JWT token for username/password."""
    user = await user_service.authenticate(payload.username, payload.password)
    if user is None:
        return 401, {"detail": "Invalid credentials"}

    now = datetime.now(UTC)
    token_payload = {
        "user_id": user.id,
        "username": user.username,
        "exp": int(
            (now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_LIFETIME)).timestamp(),
        ),
        "iat": int(now.timestamp()),
    }
    token = jwt.encode(
        token_payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return 200, {"access_token": token, "token_type": "Bearer"}


@router.get("/me", response=UserOutSchema, auth=JWTAuth())
async def get_me(request: HttpRequest) -> User:
    """Current authenticated user."""
    return request.user


@router.get(
    "/users",
    response=list[UserOutSchema],
    auth=JWTAuth(),
    by_alias=False,
)
@paginate(PageNumberPagination)
async def get_users(request: HttpRequest) -> QuerySet[User]:
    """Paginated user list via django-ninja."""
    return user_service.user_queryset()


@router.post(
    "/users",
    response={201: UserOutSchema, 400: ErrorSchema, 401: ErrorSchema, 409: ErrorSchema},
)
async def create_user(request: HttpRequest, payload: UserCreateIn) -> tuple[int, User]:
    """Create a new user."""
    user = await user_service.create_user(payload)
    return 201, user


@router.get(
    "/users/{user_id}",
    response={200: UserOutSchema, 401: ErrorSchema, 404: ErrorSchema},
    auth=JWTAuth(),
)
async def get_user(request: HttpRequest, user_id: int) -> tuple[int, User | ErrorSchema]:
    """Get user by id."""
    user = await user_service.get_user(user_id)
    if user is None:
        msg = "User not found"
        raise NotFoundError(msg)
    return 200, user


@router.put(
    "/users/{user_id}",
    response={
        200: UserOutSchema,
        400: ErrorSchema,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    },
    auth=JWTAuth(),
)
async def update_user(
    request: HttpRequest,
    user_id: int,
    payload: UserUpdateIn,
) -> tuple[int, User | ErrorSchema]:
    """Partial user update."""
    if request.user.id != user_id and not request.user.is_staff:
        msg = "No permission to edit"
        raise PermissionDeniedError(msg)

    user = await user_service.update_user(user_id, payload)
    if user is None:
        msg = "User not found"
        raise NotFoundError(msg)
    return 200, user


@router.delete(
    "/users/{user_id}",
    response={204: None, 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema},
    auth=JWTAuth(),
)
async def delete_user(request: HttpRequest, user_id: int) -> tuple[int, None]:
    """Delete a user."""
    if request.user.id != user_id and not request.user.is_staff:
        msg = "No permission to delete"
        raise PermissionDeniedError(msg)

    deleted = await user_service.delete_user(user_id)
    if not deleted:
        msg = "User not found"
        raise NotFoundError(msg)
    return 204, None


@router.get(
    "/messages",
    response=list[MessageOut],
    auth=JWTAuth(),
    by_alias=False,
)
@paginate(PageNumberPagination)
async def get_messages(
    request: HttpRequest,
    search: str | None = None,
    sort: str | None = None,
) -> QuerySet[Message]:
    """Paginated message list with search."""
    return message_service.message_queryset(search=search, sort=sort)


@router.post(
    "/messages",
    response={201: MessageOut, 400: ErrorSchema, 401: ErrorSchema},
    auth=JWTAuth(),
)
async def create_message(
    request: HttpRequest,
    payload: MessageIn,
) -> tuple[int, MessageOut]:
    """Create a message."""
    message = await message_service.create_message(request.user.id, payload.content)
    return 201, MessageOut(
        id=message.id,
        content=message.content,
        timestamp=message.timestamp,
        sender=request.user.username,
    )


@router.delete(
    "/messages/{message_id}",
    response={
        200: OperationResultSchema,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    },
    auth=JWTAuth(),
)
async def delete_message(
    request: HttpRequest,
    message_id: int,
) -> tuple[int, dict[str, str]]:
    """Delete a message."""
    message = await message_service.get_message(message_id)
    if message is None:
        msg = "Message not found"
        raise NotFoundError(msg)
    if message.sender_id != request.user.id and not request.user.is_staff:
        msg = "No permission to delete message"
        raise PermissionDeniedError(msg)

    await message_service.delete_message(message_id)
    return 200, {"detail": "Message deleted"}


@router.get(
    "/photos",
    response=list[PhotoOut],
    auth=JWTAuth(),
    by_alias=False,
)
@paginate(PageNumberPagination)
async def get_photos(request: HttpRequest) -> QuerySet[Photo]:
    """List photos for the current user."""
    return photo_service.photo_queryset(request.user.id)


@router.post(
    "/photos",
    response={201: PhotoOut, 400: ErrorSchema, 401: ErrorSchema},
    auth=JWTAuth(),
)
async def create_photo(
    request: HttpRequest,
    file: UploadedFile = File(...),
) -> tuple[int, PhotoOut]:
    """Upload a photo."""
    photo = await photo_service.create_photo(request.user.id, file)
    return 201, PhotoOut(
        id=photo.id,
        image=photo.image.url if photo.image else "",
        user_id=photo.user_id,
    )
