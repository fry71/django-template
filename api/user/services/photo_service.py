# api/user/services/photo_service.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from api.common.exceptions import ValidationError
from api.user.models import Photo

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile
    from django.db.models import QuerySet

logger = logging.getLogger(__name__)

_MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5MB


def photo_queryset(user_id: int) -> QuerySet[Photo]:
    """Queryset of photos for a user."""
    return Photo.objects.filter(user_id=user_id).order_by("-uploaded_at")


async def create_photo(user_id: int, uploaded: UploadedFile) -> Photo:
    """Create a photo record — simple write (single INSERT)."""
    content_type = uploaded.content_type or ""
    if not content_type.startswith("image/"):
        msg = "Only image files are allowed"
        raise ValidationError(msg, fields={"image": [msg]})

    if uploaded.size > _MAX_PHOTO_SIZE:
        msg = "File size must not exceed 5MB"
        raise ValidationError(msg, fields={"image": [msg]})

    photo = await Photo.objects.acreate(user_id=user_id, image=uploaded)
    logger.info("Photo created: %s", photo.id)
    return photo
