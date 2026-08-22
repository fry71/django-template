# api/user/admin.py
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from api.user.models import Message, Photo, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model."""

    list_display = [
        "email",
        "first_name",
        "last_name",
        "phone",
        "is_staff",
        "is_active",
        "date_joined",
    ]
    list_filter = ["is_staff", "is_active", "is_superuser", "date_joined"]
    search_fields = ["email", "first_name", "last_name", "phone"]
    ordering = ["email"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal info"),
            {"fields": ("first_name", "last_name", "patronymic", "phone", "bio")},
        ),
        (_("Profile"), {"fields": ("photo",)}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "patronymic",
                    "phone",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )

    readonly_fields = ["last_login", "date_joined"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for Message model."""

    list_display = ["sender", "content_preview", "timestamp"]
    list_filter = ["timestamp"]
    search_fields = ["sender__username", "sender__email", "content"]
    readonly_fields = ["timestamp"]
    date_hierarchy = "timestamp"

    def content_preview(self, obj: Message) -> str:
        """Return preview of message content."""
        preview_length = 50
        content = obj.content
        if len(content) <= preview_length:
            return content
        preview = content[:preview_length]
        return f"{preview}..."

    content_preview.short_description = _("Content preview")


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    """Admin interface for Photo model."""

    list_display = ["user", "image_preview", "uploaded_at"]
    list_filter = ["uploaded_at"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["uploaded_at", "image_preview"]

    def image_preview(self, obj: Photo) -> str:
        """Return image preview."""
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 100px; height: auto;" />',
                obj.image.url,
            )
        return str(_("No image"))

    image_preview.short_description = _("Preview")
