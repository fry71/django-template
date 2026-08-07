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


class Message(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Message"
        verbose_name_plural = "Messages"

    def __str__(self) -> str:
        return f"{self.sender.username}: {self.content[:20]}"


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
        return f"{self.user.username} - {self.image.name}"
