# api/user/services/photo_service.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from api.common.exceptions import ValidationError
from api.user.limits import ALLOWED_IMAGE_PREFIX, MAX_PHOTO_SIZE_BYTES
from api.user.models import Photo

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from api.user.services.cmds import ListPhotosQuery, UploadPhotoCmd

logger = logging.getLogger(__name__)


def photo_queryset(cmd: ListPhotosQuery) -> QuerySet[Photo]:
    """Queryset of photos for a user."""
    return Photo.objects.filter(user_id=cmd.user_id).order_by("-uploaded_at")


async def create_photo(cmd: UploadPhotoCmd) -> Photo:
    """Create a photo record — simple write (single INSERT).

    The API also validates the same limits at the boundary (see
    ``schema.PhotoUploadMeta``); these checks keep the domain invariant
    for non-HTTP callers such as tasks and the bot.
    """
    uploaded = cmd.uploaded
    content_type = uploaded.content_type or ""
    if not content_type.startswith(ALLOWED_IMAGE_PREFIX):
        msg = "Only image files are allowed"
        raise ValidationError(msg, fields={"image": [msg]})

    if uploaded.size and uploaded.size > MAX_PHOTO_SIZE_BYTES:
        msg = "File size must not exceed 5MB"
        raise ValidationError(msg, fields={"image": [msg]})

    photo = await Photo.objects.acreate(user_id=cmd.user_id, image=uploaded)
    logger.info("Photo created: %s", photo.id)
    return photo
