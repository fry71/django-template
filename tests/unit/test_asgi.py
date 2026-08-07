# tests/unit/test_asgi.py
from __future__ import annotations

from pathlib import Path

import pytest

from api.web import asgi as asgi_module

MEDIA_URL = "/media/"
MEDIA_ROOT = Path("/tmp/opencode/test_media")


@pytest.fixture(autouse=True)
def _media_root(monkeypatch) -> None:
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(asgi_module.settings, "MEDIA_URL", MEDIA_URL)
    monkeypatch.setattr(asgi_module.settings, "MEDIA_ROOT", str(MEDIA_ROOT))
    yield
    for f in MEDIA_ROOT.iterdir():
        f.unlink()


async def _send_file(name: str, content: bytes) -> None:
    (MEDIA_ROOT / name).write_bytes(content)


def _make_scope(path: str, type_: str = "http") -> dict:
    return {"type": type_, "path": path}


class _SendCollector:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def __call__(self, event: dict) -> None:
        self.events.append(event)


class TestServeMedia:
    async def test_serves_existing_file(self) -> None:
        await _send_file("logo.txt", b"hello media")
        send = _SendCollector()

        result = await asgi_module.serve_media(_make_scope("/media/logo.txt"), None, send)

        assert result is None
        start = send.events[0]
        assert start["type"] == "http.response.start"
        assert start["status"] == 200
        assert dict(start["headers"])[b"Content-Type"] == b"text/plain"
        body = send.events[1]
        assert body["body"] == b"hello media"

    async def test_returns_404_for_missing_file(self) -> None:
        send = _SendCollector()
        await asgi_module.serve_media(_make_scope("/media/missing.txt"), None, send)

        assert send.events[0]["type"] == "http.response.start"
        assert send.events[0]["status"] == 404
        assert send.events[1]["body"] == b"File not found"

    async def test_forwards_non_media_request(self) -> None:
        forwarded: list[dict] = []

        async def fake_django(scope, receive, send) -> None:
            forwarded.append(scope)

        original = asgi_module.django_application
        asgi_module.django_application = fake_django  # type: ignore[assignment]
        try:
            await asgi_module.serve_media(
                _make_scope("/api/user/me"), None, _SendCollector()
            )
        finally:
            asgi_module.django_application = original

        assert forwarded, "non-media path should be forwarded to Django"

    async def test_forwards_websocket(self) -> None:
        forwarded: list[dict] = []

        async def fake_django(scope, receive, send) -> None:
            forwarded.append(scope)

        original = asgi_module.django_application
        asgi_module.django_application = fake_django  # type: ignore[assignment]
        try:
            await asgi_module.serve_media(
                _make_scope("/media/whatever", type_="websocket"),
                None,
                _SendCollector(),
            )
        finally:
            asgi_module.django_application = original

        assert forwarded, "websocket scope should be forwarded to Django"
