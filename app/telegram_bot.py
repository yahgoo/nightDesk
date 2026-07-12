"""Telegram bot entrypoint for NightDesk.

Single responsibility: run the aiogram bot that receives Telegram updates, enforces
the allow-list of users (TELEGRAM_ALLOWED_USERS), and forwards every message to the
Manager Agent — then sends the agent's reply (and any voice note) back to the user.
It owns no business logic itself; it is the transport between Telegram and the agent
orchestration.
"""
from __future__ import annotations

import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.logging_utils import conversation_id_ctx, log_event
from app.manager_agent import ManagerAgent

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USERS = {
    u.strip() for u in os.environ.get("TELEGRAM_ALLOWED_USERS", "").split(",") if u.strip()
}

manager = ManagerAgent()
bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()


def _allowed(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True  # dev mode: allow all when no allow-list is set
    return str(user_id) in ALLOWED_USERS


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Hi! I'm NightDesk, your after-hours booking assistant. "
        "Tell me what you'd like to book, cancel, or reschedule."
    )


@dp.message(F.text)
async def on_text(message: Message) -> None:
    if not _allowed(message.from_user.id):
        await message.answer("Sorry, you're not authorised to use this bot.")
        return
    conversation_id = str(message.chat.id)
    conversation_id_ctx.set(conversation_id)
    log_event("telegram_bot", "message_received",
              {"user_id": message.from_user.id, "text": message.text})
    reply = await manager.handle(
        str(message.from_user.id), message.text, conversation_id=conversation_id)
    await message.answer(reply)


async def start_polling() -> None:
    if not bot:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set; cannot start the bot.")
    log_event("telegram_bot", "bot_started", {})
    await dp.start_polling(bot)


def main() -> None:
    import asyncio

    asyncio.run(start_polling())


if __name__ == "__main__":
    main()
