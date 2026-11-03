# api/user/limits.py
"""Domain limits shared by the API boundary and the service layer."""

from __future__ import annotations

from typing import Final

MAX_PHOTO_SIZE_BYTES: Final = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_PREFIX: Final = "image/"
