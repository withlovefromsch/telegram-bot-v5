"""Раздел помощи / техподдержки."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message

from config import SUPPORT_USERNAME

router = Router()


@router.message(F.text == "❓ Помощь")
async def show_help(message: Message) -> None:
    await message.answer(
        "❓ <b>Помощь и поддержка</b>\n\n"
        "Если у вас возникли вопросы по оплате, доступу к курсам или другим темам — "
        "свяжитесь с нашей технической поддержкой:\n\n"
        f"💬 <b>Написать в поддержку:</b> {SUPPORT_USERNAME}\n\n"
        "⏱ Время работы: ежедневно с 9:00 до 21:00"
    )
