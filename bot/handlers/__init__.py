# bot/handlers/__init__.py
from __future__ import annotations

from aiogram import Router

from bot.handlers.echo import router as echo_router
from bot.handlers.start import router as start_router

router = Router(name="root")
router.include_routers(start_router, echo_router)

__all__ = ["router"]
