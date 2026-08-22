# bot/handlers/echo.py
from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router

if TYPE_CHECKING:
    from aiogram.types import Message

router = Router(name="echo")


@router.message(F.text)
async def echo_text(message: Message) -> None:
    """Echo any plain-text message back to the sender."""
    await message.answer(message.text or "")


@router.message()
async def fallback(message: Message) -> None:
    """Fallback for non-text content."""
    await message.answer("I understand only text messages for now.")
