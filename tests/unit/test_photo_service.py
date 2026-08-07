# tests/unit/test_photo_service.py
from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from api.common.exceptions import ValidationError
from api.user.models import Photo
from api.user.services import photo_service


def _make_file(name: str, content: bytes, content_type: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type=content_type)


@pytest.mark.django_db(transaction=True)
class TestPhotoService:
    async def test_create_photo(self, test_user) -> None:
        file = _make_file("photo.png", b"\x89PNG\r\n\x1a\nfake-image", "image/png")
        photo = await photo_service.create_photo(test_user.id, file)

        assert photo.user_id == test_user.id
        assert await Photo.objects.filter(id=photo.id).aexists()
        assert photo.image is not None

    async def test_create_photo_rejects_non_image(self, test_user) -> None:
        file = _make_file("notes.txt", b"just text", "text/plain")
        with pytest.raises(ValidationError) as exc_info:
            await photo_service.create_photo(test_user.id, file)
        assert "Only image files" in str(exc_info.value)

    async def test_create_photo_rejects_too_large(self, test_user) -> None:
        # 5MB limit: 5 * 1024 * 1024 + 1 byte
        oversized = b"\0" * (5 * 1024 * 1024 + 1)
        file = _make_file("big.png", oversized, "image/png")
        with pytest.raises(ValidationError) as exc_info:
            await photo_service.create_photo(test_user.id, file)
        assert "5MB" in str(exc_info.value)

    async def test_photo_queryset_filters_by_user(self, test_user) -> None:
        file = _make_file("a.png", b"png", "image/png")
        photo = await photo_service.create_photo(test_user.id, file)

        qs = photo_service.photo_queryset(test_user.id)
        photos = [p async for p in qs]
        assert photos == [photo]

        qs_other = photo_service.photo_queryset(999_999)
        assert [p async for p in qs_other] == []


@pytest.mark.django_db(transaction=True)
class TestPhotoServiceIoErrors:
    async def test_create_photo_with_empty_content_type(self, test_user) -> None:
        file = _make_file("photo.bin", b"x", "")
        with pytest.raises(ValidationError):
            await photo_service.create_photo(test_user.id, file)
