# Copyright (c) 2025 Fedorov Dmitry
# Licensed under the MIT License. See LICENSE file in the project root for details.

from __future__ import annotations

import json
import logging

import jwt
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from .models import Message, User

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat functionality."""

    async def connect(self) -> None:
        """Handle new WebSocket connection."""
        logger.info("WebSocket connecting...")

        # Extract token from URL
        token = self.scope["url_route"]["kwargs"].get("token")
        if not token:
            logger.error("No token provided")
            await self.close()
            return

        logger.info("WebSocket connected with token: %s", token)

        try:
            # Decode JWT token
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            user_id = payload["user_id"]

            # Get user asynchronously
            self.user = await User.objects.aget(id=user_id)
            self.group_name = "chat_group"

            # Add to channel group
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

            logger.info("User %s connected to chat", self.user.username)

        except jwt.InvalidTokenError:
            logger.exception("Invalid JWT token")
            await self.close()
        except User.DoesNotExist:
            logger.exception("User not found")
            await self.close()
        except Exception:
            logger.exception("Error during connection")
            await self.close()

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

        try:
            data = json.loads(text_data)
            content = data.get("content")

            if content:
                # Create message asynchronously
                message = await Message.objects.acreate(sender=self.user, content=content)

                formatted_date = message.timestamp.strftime("%Y-%m-%d %H:%M")

                # Broadcast message to group
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "chat_message",
                        "message": {
                            "content": message.content,
                            "timestamp": formatted_date,
                            "username": self.user.username,
                        },
                    },
                )

                logger.info("Message sent by %s: %s", self.user.username, content)
            else:
                logger.warning("Received empty message content")

        except json.JSONDecodeError:
            logger.exception("Invalid JSON received")
        except Exception:
            logger.exception("Error processing message")

    async def chat_message(self, event: dict) -> None:
        """Handle chat messages from channel layer."""
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
