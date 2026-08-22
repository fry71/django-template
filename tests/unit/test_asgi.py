# tests/unit/test_asgi.py
from __future__ import annotations

from api.web.asgi import application


class TestASGIApplication:
    def test_application_built(self) -> None:
        assert application is not None

    def test_http_routed_to_django(self) -> None:
        assert application.application_mapping["http"] is not None

    def test_websocket_routed_to_channels(self) -> None:
        ws = application.application_mapping["websocket"]
        assert ws is not None
