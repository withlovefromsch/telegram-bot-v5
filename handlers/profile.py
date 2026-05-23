"""Личный кабинет пользователя."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message

from database import db

router = Router()

# Статусы заказов — русские названия
ORDER_STATUS_MAP = {
    "new":              "🆕 Новая",
    "in_work":          "🔄 В работе",
    "waiting_payment":  "💳 Ожидает оплаты",
    "payment_received": "📸 Оплата получена",
    "verifying":        "🔍 Проверяется",
    "completed":        "✅ Завершена",
    "cancelled":        "❌ Отменена",
}


@router.message(F.text == "👤 Личный кабинет")
async def show_profile(message: Message) -> None:
    user = await db.get_user(message.from_user.id)  # type: ignore[arg-type]
    if not user:
        await message.answer("⚠️ Вы не зарегистрированы. Нажмите /start")
        return

    orders = await db.get_user_orders(user["id"])

    orders_text = ""
    if orders:
        orders_text = "\n\n📦 <b>Мои заявки:</b>\n"
        for o in orders:
            status_label = ORDER_STATUS_MAP.get(o["status"], o["status"])
            orders_text += f"  • Заявка <b>#{o['id']}</b> — {status_label}\n"
    else:
        orders_text = "\n\n📦 У вас пока нет заявок."

    username_line = f"@{user['username']}" if user["username"] else "не указан"
    await message.answer(
        "👤 <b>Личный кабинет</b>\n\n"
        f"🏷 Имя: {user['name']}\n"
        f"📱 Username: {username_line}\n"
        f"☎️ Телефон: {user['phone']}\n"
        f"📧 Email: {user['email']}"
        + orders_text,
    )
