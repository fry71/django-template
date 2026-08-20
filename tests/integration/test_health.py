# tests/integration/test_health.py
from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_returns_ok() -> None:
    """The liveness endpoint returns 200 with a JSON status."""
    response = Client().get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
