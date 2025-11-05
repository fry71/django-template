# Copyright (c) 2025 Fedorov Dmitry
# Licensed under the MIT License. See LICENSE file in the project root for details.

from channels.generic.websocket import AsyncWebsocketConsumer
import json
import jwt
from django.conf import settings
from asgiref.sync import sync_to_async
from .models import User, Message
import logging

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat functionality"""

    async def connect(self):
        """Handle new WebSocket connection"""
        logger.info("WebSocket connecting...")

        # Extract token from URL
        token = self.scope["url_route"]["kwargs"].get("token")
        if not token:
            logger.error("No token provided")
            await self.close()
            return

        logger.info(f"WebSocket connected with token: {token}")

        try:
            # Decode JWT token
            payload = jwt.decode(
                token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
            user_id = payload["user_id"]

            # Get user asynchronously
            self.user = await User.objects.aget(id=user_id)
            self.group_name = "chat_group"

            # Add to channel group
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

            logger.info(f"User {self.user.username} connected to chat")

        except jwt.InvalidTokenError:
            logger.error("Invalid JWT token")
            await self.close()
        except User.DoesNotExist:
            logger.error("User not found")
            await self.close()
        except Exception as e:
            logger.error(f"Error during connection: {e}")
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        logger.info(f"WebSocket disconnected with code: {close_code}")

        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        if hasattr(self, "user"):
            logger.info(f"User {self.user.username} disconnected from chat")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
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

                logger.info(f"Message sent by {self.user.username}: {content}")
            else:
                logger.warning("Received empty message content")

        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def chat_message(self, event):
        """Handle chat messages from channel layer"""
        message = event["message"]

        try:
            await self.send(
                text_data=json.dumps(
                    {
                        "content": message["content"],
                        "timestamp": message["timestamp"],
                        "username": message["username"],
                    }
                )
            )
        except Exception as e:
            logger.error(f"Error sending message to client: {e}")
