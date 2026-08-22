# bot/handlers/start.py
from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart

if TYPE_CHECKING:
    from aiogram.types import Message

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    """Handle /start — greet and show a short hint."""
    payload = command.args
    greeting = "Hi! I am your assistant bot."
    if payload:
        greeting += f"\nYou came with payload: {payload}"
    await message.answer(greeting)


@router.message(F.text == "/help")
async def cmd_help(message: Message) -> None:
    """Handle /help — list available commands."""
    await message.answer(
        "Available commands:\n"
        "/start — start the bot\n"
        "/help — show this help\n"
        "Anything else you send will be echoed back.",
    )
