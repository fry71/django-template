# Copyright (c) 2025 Fedorov Dmitry
# Licensed under the MIT License. See LICENSE file in the project root for details.

from __future__ import annotations

import json
import logging

import jwt
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from api.user.models import Message, User

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat functionality."""

    async def connect(self) -> None:
        """Handle a new WebSocket connection."""
        logger.info("WebSocket connecting...")
        if not await self._authenticate():
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info("User %s connected to chat", self.user.username)

    async def disconnect(self, close_code: int | None) -> None:
        """Handle WebSocket disconnection."""
        logger.info("WebSocket disconnected with code: %s", close_code)
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if hasattr(self, "user"):
            logger.info("User %s disconnected from chat", self.user.username)

    async def receive(self, text_data: str | None) -> None:
        """Handle incoming WebSocket messages."""
        if not hasattr(self, "group_name"):
            logger.warning("Received message before connection established")
            return
        if not text_data:
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

    async def _authenticate(self) -> bool:
        """Authenticate the user from the JWT token in the URL.

        Returns whether the connection may proceed.
        """
        token = self.scope["url_route"]["kwargs"].get("token")
        if not token:
            logger.error("No token provided")
            await self.close()
            return False
        try:
            self.user = await self._resolve_user(token)
        except jwt.InvalidTokenError, User.DoesNotExist, KeyError:
            logger.exception("WebSocket authentication failed")
            await self.close()
            return False
        self.group_name = "chat_group"
        return True

    async def _resolve_user(self, token: str) -> User:
        """Resolve a user from a valid JWT token."""
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return await User.objects.aget(id=payload["user_id"])

    async def _broadcast_message(self, text_data: str) -> None:
        """Parse a chat message and broadcast it to the group."""
        try:
            message_data = json.loads(text_data)
        except json.JSONDecodeError:
            logger.exception("Invalid JSON received")
            return
        content = message_data.get("content")
        if not content:
            logger.warning("Received empty message content")
            return
        message = await Message.objects.acreate(sender=self.user, content=content)
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
