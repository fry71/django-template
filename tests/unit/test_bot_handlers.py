# tests/unit/test_bot_handlers.py
from __future__ import annotations

from bot.handlers import router as root_router
from bot.handlers.echo import router as echo_router
from bot.handlers.start import router as start_router


class TestBotRouters:
    def test_root_includes_subrouters(self) -> None:
        names = [r.name for r in root_router.sub_routers]
        assert "start" in names
        assert "echo" in names

    def test_start_has_command_handlers(self) -> None:
        assert len(start_router.message.handlers) >= 1

    def test_echo_has_text_and_fallback(self) -> None:
        assert len(echo_router.message.handlers) == 2
