# tests/unit/test_throttling.py
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

import pytest

from api.common.throttling import UsernameFromBody


@dataclass
class _StubController:
    request: Any


def _controller(body: bytes) -> _StubController:
    return _StubController(request=type("_Request", (), {"body": body})())


def test_key_is_hash_of_username() -> None:
    key = UsernameFromBody()(None, _controller(b'{"username": "Alice"}'))  # type: ignore[arg-type]

    assert key == sha256(b"alice").hexdigest()
    assert "alice" not in key


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"not-json",
        b"{}",
        b'{"username": ""}',
        b'{"username": 42}',
        b'["username"]',
    ],
)
def test_key_is_skipped_without_username(body: bytes) -> None:
    assert UsernameFromBody()(None, _controller(body)) is None  # type: ignore[arg-type]
