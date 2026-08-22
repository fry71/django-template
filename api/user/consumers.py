# Copyright (c) 2025 Fedorov Dmitry
# Licensed under the MIT License. See LICENSE file in the project root for details.

from __future__ import annotations

import json
import logging
import time

import jwt
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from api.user.models import User
from api.user.services import message_service, room_service

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 4000
RATE_LIMIT_MESSAGES = 10
RATE_LIMIT_WINDOW_SECONDS = 5.0


class SlidingWindowRateLimiter:
    """Per-connection sliding-window rate limiter."""

    def __init__(self, max_messages: int, window_seconds: float) -> None:
        self._max_messages = max_messages
        self._window_seconds = window_seconds
        self._send_times: list[float] = []

    def allows(self) -> bool:
        """Return whether the current event is within the allowed rate."""
        now = time.monotonic()
        window_start = now - self._window_seconds
        self._send_times = [sent for sent in self._send_times if sent > window_start]
        if len(self._send_times) >= self._max_messages:
            return False
        self._send_times.append(now)
        return True


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat functionality."""

    async def connect(self) -> None:
        """Accept the socket; auth is the first JSON frame (not a query token)."""
        logger.info("WebSocket connecting...")
        room_id = self.scope["url_route"]["kwargs"].get("room_id")
        if not room_id:
            await self.close()
            return
        self.room_id = int(room_id)
        self._authenticated = False
        await self.accept()

    async def disconnect(self, close_code: int | None) -> None:
        """Handle WebSocket disconnection."""
        logger.info("WebSocket disconnected with code: %s", close_code)
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if hasattr(self, "user"):
            logger.info("User %s disconnected from chat", self.user.username)

    async def receive(self, text_data: str | None) -> None:
        """Handle incoming WebSocket messages."""
        if not hasattr(self, "room_id") or not text_data:
            return
        if not self._authenticated:
            await self._authenticate_first_frame(text_data)
            return
        await self._broadcast_message(text_data)

    async def chat_message(self, event: dict) -> None:
        """Handle chat messages from the channel layer."""
        message = event["message"]
        try:
            await self.send(
                text_data=json.dumps(
                    {
                        "content": message["content"],
                        "timestamp": message["timestamp"],
                        "username": message["username"],
                    },
                ),
            )
        except Exception:
            logger.exception("Error sending message to client")

    async def _authenticate_first_frame(self, text_data: str) -> None:
        """Authenticate from ``{"type": "auth", "token": "<access JWT>"}``."""
        token = _extract_auth_token(text_data)
        if token is None:
            logger.error("First WebSocket frame must be an auth message")
            await self.close()
            return
        if not await _bind_user(self, token):
            return
        if not await room_service.is_member(self.room_id, self.user.id):
            logger.warning(
                "User %s is not a member of room %s",
                self.user.username,
                self.room_id,
            )
            await self.close()
            return
        await self._join_room_group()

    async def _join_room_group(self) -> None:
        """Subscribe the socket to the room channel group."""
        self.group_name = f"chat_{self.room_id}"
        self._rate_limiter = SlidingWindowRateLimiter(
            max_messages=RATE_LIMIT_MESSAGES,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        )
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        self._authenticated = True
        await self.send(text_data=json.dumps({"type": "auth_ok"}))
        logger.info("User %s connected to chat", self.user.username)

    async def _broadcast_message(self, text_data: str) -> None:
        """Parse a chat message and broadcast it to the group."""
        if not self._rate_limiter.allows():
            logger.warning("Rate limit exceeded for user %s", self.user.username)
            await self.send(text_data=json.dumps({"error": "rate_limited"}))
            return
        try:
            message_data = json.loads(text_data)
        except json.JSONDecodeError:
            logger.exception("Invalid JSON received")
            return
        content = message_data.get("content")
        if not content:
            logger.warning("Received empty message content")
            return
        if len(content) > MAX_CONTENT_LENGTH:
            await self.send(text_data=json.dumps({"error": "content_too_long"}))
            return
        message = await message_service.create_message(
            sender_id=self.user.id,
            room_id=self.room_id,
            message_content=content,
        )
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat_message",
                "message": {
                    "content": message.content,
                    "timestamp": message.timestamp.strftime("%Y-%m-%d %H:%M"),
                    "username": self.user.username,
                },
            },
        )
        logger.info("Message sent by %s: %s", self.user.username, content)


async def _bind_user(consumer: ChatConsumer, token: str) -> bool:
    """Resolve JWT to ``consumer.user``. Return whether auth may continue."""
    try:
        consumer.user = await _user_from_access_token(token)
    except jwt.InvalidTokenError, User.DoesNotExist, KeyError:
        logger.exception("WebSocket authentication failed")
        await consumer.close()
        return False
    return True


async def _user_from_access_token(token: str) -> User:
    """Resolve a user from a valid access JWT token."""
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    extras = payload.get("extras", {})
    token_type = extras.get("type") or payload.get("token_type")
    if token_type != "access":
        msg = "Refresh token used for WebSocket auth"
        raise jwt.InvalidTokenError(msg)
    return await User.objects.aget(id=payload["user_id"])


def _extract_auth_token(text_data: str) -> str | None:
    """Return the access token from a first-frame auth payload, or None."""
    try:
        payload = json.loads(text_data)
    except json.JSONDecodeError:
        return None
    if payload.get("type") != "auth":
        return None
    token = payload.get("token")
    if not isinstance(token, str) or not token:
        return None
    return token
