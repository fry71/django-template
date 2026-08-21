# api/user/models.py
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    phone = models.CharField(max_length=255, blank=True, null=True, default=None)
    patronymic = models.CharField(max_length=255, blank=True, null=True, default=None)
    bio = models.TextField(max_length=500, blank=True, null=True, default=None)
    photo = models.ImageField(upload_to="profile_photos/", null=True, blank=True)

    REQUIRED_FIELDS = ["email"]

    def __str__(self) -> str:
        return self.username

    @property
    def full_name(self) -> str:
        """Returns user's full name."""
        parts = [self.last_name, self.first_name, self.patronymic]
        return " ".join(part for part in parts if part) or self.username


class RoomType(models.TextChoices):
    """Types of chat rooms."""

    GROUP = "group", "Group"
    DIRECT = "direct", "Direct"


class ChatRoom(models.Model):
    """Chat room: group chat or 1:1 direct conversation."""

    name = models.CharField(max_length=255)
    room_type = models.CharField(
        max_length=10,
        choices=RoomType.choices,
        default=RoomType.GROUP,
    )
    is_private = models.BooleanField(default=False)
    direct_key = models.CharField(
        max_length=80,
        null=True,
        blank=True,
        default=None,
        unique=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_rooms",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="RoomMembership",
        related_name="chat_rooms",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Chat room"
        verbose_name_plural = "Chat rooms"

    def __str__(self) -> str:
        return f"{self.name} ({self.room_type})"


class RoomMembership(models.Model):
    """Membership of a user in a chat room."""

    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="room_memberships",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["room", "user"],
                name="unique_room_membership",
            ),
        ]
        ordering = ["joined_at"]

    def __str__(self) -> str:
        member_name = self.user.username
        room_name = self.room.name
        return f"{member_name} in {room_name}"


def direct_room_key(user_a_id: int, user_b_id: int) -> str:
    """Deterministic key identifying a 1:1 room between two users."""
    low, high = sorted((user_a_id, user_b_id))
    return f"direct:{low}:{high}"


class UsedRefreshToken(models.Model):
    """Denylist of already-rotated refresh tokens (by jti)."""

    jti = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Used refresh token"
        verbose_name_plural = "Used refresh tokens"

    def __str__(self) -> str:
        return self.jti


class Message(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Message"
        verbose_name_plural = "Messages"

    def __str__(self) -> str:
        sender_name = self.sender.username
        message_preview = self.content[:20]
        return f"{sender_name}: {message_preview}"


class Photo(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(upload_to="photos/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Photo"
        verbose_name_plural = "Photos"

    def __str__(self) -> str:
        owner_name = self.user.username
        file_name = self.image.name
        return f"{owner_name} - {file_name}"
