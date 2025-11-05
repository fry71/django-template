# api/user/api.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
import re

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import aauthenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest
import jwt
from ninja import Query, Router, UploadedFile, File
from ninja.security import HttpBearer
from typing import List

from .models import Message, User, Photo
from .schema import (
    UserTokenSchema,
    UserLoginSchema,
    UserSchema,
    UserCreateSchema,
    UserUpdateSchema,
    PaginatedUsersOut,
    PaginatedMessagesOut,
    MessageSchema,
    MessageInSchema,
    PhotoSchema,
    ErrorSchema,
)

logger = logging.getLogger(__name__)

router = Router()


class JWTAuth(HttpBearer):
    async def authenticate(self, request: HttpRequest, token: str) -> Optional[User]:
        try:
            payload = jwt.decode(
                token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
            user_id = payload.get("user_id")
            if not user_id:
                return None
            user = await User.objects.aget(id=user_id)
            request.user = user
            return user
        except (jwt.InvalidTokenError, User.DoesNotExist) as e:
            logger.error(f"JWT Error: {e}")
            return None


def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


@router.post("/token", response={200: UserTokenSchema, 401: ErrorSchema})
async def get_token(request, payload: UserLoginSchema):
    logger.debug(f"Login attempt: {payload}")
    user = await aauthenticate(username=payload.username, password=payload.password)
    if not user:
        return 401, {"detail": "Invalid credentials"}

    now = datetime.now(timezone.utc)
    token_payload = {
        "user_id": user.id,
        "username": user.username,
        "exp": int(
            (now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_LIFETIME)).timestamp()
        ),
        "iat": int(now.timestamp()),
    }
    token = jwt.encode(
        token_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return {"access_token": token, "token_type": "Bearer"}


@router.get("/me", response=UserSchema, auth=JWTAuth())
async def get_me(request):
    return request.user


@router.get("/users", response=PaginatedUsersOut, auth=JWTAuth())
async def get_users(
    request,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
):
    users_qs = User.objects.all().order_by("-id")
    users_list = await sync_to_async(list)(users_qs)
    paginator = Paginator(users_list, per_page)
    page_obj = paginator.get_page(page)
    results = [user for user in page_obj.object_list]

    return {
        "count": paginator.count,
        "results": results,
    }


@router.post("/users", response={201: UserSchema, 400: ErrorSchema})
async def create_user(request, payload: UserCreateSchema):
    try:
        if not validate_email(payload.email):
            return 400, {"detail": "Invalid email format"}

        validate_password(payload.password)

        try:
            await User.objects.aget(email=payload.email)
            return 400, {"detail": "Email already exists"}
        except User.DoesNotExist:
            pass

        user = await User.objects.acreate_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
            patronymic=payload.patronymic,
        )
        return 201, user
    except ValidationError as e:
        return 400, {"detail": "; ".join(e.messages)}
    except Exception as e:
        return 400, {"detail": str(e)}


@router.get(
    "/users/{user_id}",
    response={200: UserSchema, 404: ErrorSchema},
    auth=JWTAuth(),
)
async def get_user(request, user_id: int):
    try:
        user = await User.objects.aget(id=user_id)
        return user
    except User.DoesNotExist:
        return 404, {"detail": "User not found"}


@router.put(
    "/users/{user_id}",
    response={200: UserSchema, 404: ErrorSchema},
    auth=JWTAuth(),
)
async def update_user(request, user_id: int, payload: UserUpdateSchema):
    if request.user.id != user_id and not request.user.is_staff:
        return 403, {"detail": "No permission to edit"}

    try:
        user = await User.objects.aget(id=user_id)
        update_data = payload.model_dump(exclude_unset=True)

        if "email" in update_data and update_data["email"]:
            if not validate_email(update_data["email"]):
                return 400, {"detail": "Invalid email format"}

            try:
                existing_user = await User.objects.exclude(id=user_id).aget(
                    email=update_data["email"]
                )
                return 400, {"detail": "Email already exists"}
            except User.DoesNotExist:
                pass

        for key, value in update_data.items():
            setattr(user, key, value)
        await user.asave()
        return user
    except User.DoesNotExist:
        return 404, {"detail": "User not found"}


@router.delete("/users/{user_id}", response={204: None, 404: ErrorSchema}, auth=JWTAuth())
async def delete_user(request, user_id: int):
    if request.user.id != user_id and not request.user.is_staff:
        return 403, {"detail": "No permission to delete"}

    try:
        user = await User.objects.aget(id=user_id)
        await user.adelete()
        return 204, None
    except User.DoesNotExist:
        return 404, {"detail": "User not found"}


@router.get("/messages", response=PaginatedMessagesOut, auth=JWTAuth())
async def get_messages(
    request,
    search: Optional[str] = None,
    sort: Optional[str] = "-id",
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
):
    messages_qs = Message.objects.select_related("sender").all().order_by(sort or "-id")
    messages_list = await sync_to_async(list)(messages_qs)

    if search:
        messages_list = [m for m in messages_list if search.lower() in m.content.lower()]

    paginator = Paginator(messages_list, per_page)
    page_obj = paginator.get_page(page)

    results = [
        MessageSchema(
            id=message.id,
            content=message.content,
            timestamp=message.timestamp,
            sender=message.sender.username,
        )
        for message in page_obj.object_list
    ]

    return {
        "count": paginator.count,
        "search": search,
        "sort": sort,
        "results": results,
    }


@router.post(
    "/messages",
    response={201: MessageSchema, 400: ErrorSchema},
    auth=JWTAuth(),
)
async def create_message(request, payload: MessageInSchema):
    try:
        message = await Message.objects.acreate(
            sender=request.user, content=payload.content
        )
        return 201, MessageSchema(
            id=message.id,
            content=message.content,
            timestamp=message.timestamp,
            sender=message.sender.username,
        )
    except Exception as e:
        return 400, {"detail": str(e)}


@router.delete(
    "/messages/{message_id}",
    response={204: None, 404: ErrorSchema},
    auth=JWTAuth(),
)
async def delete_message(request, message_id: int):
    try:
        message = await Message.objects.aget(id=message_id)
        if message.sender != request.user and not request.user.is_staff:
            return 403, {"detail": "No permission to delete message"}
        await message.adelete()
        return 204, None
    except Message.DoesNotExist:
        return 404, {"detail": "Message not found"}


@router.get("/photos", response=List[PhotoSchema], auth=JWTAuth())
async def get_photos(request):
    photos = await sync_to_async(list)(Photo.objects.filter(user=request.user).all())
    return photos


@router.post("/photos", response={201: PhotoSchema, 400: ErrorSchema}, auth=JWTAuth())
async def create_photo(request, file: UploadedFile = File(...)):
    try:
        # Validate file type
        if not file.content_type.startswith("image/"):
            return 400, {"detail": "Only image files are allowed"}

        # Validate file size (5MB limit)
        if file.size > 5 * 1024 * 1024:
            return 400, {"detail": "File size must not exceed 5MB"}

        # Save file and create photo record
        photo = await Photo.objects.acreate(user=request.user, image=file)
        return 201, photo
    except Exception as e:
        logger.error(f"Error creating photo: {e}")
        return 400, {"detail": str(e)}
