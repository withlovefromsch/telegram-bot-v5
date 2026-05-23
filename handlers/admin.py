"""Административная панель — управление заявками."""
from __future__ import annotations

import logging

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADMIN_IDS
from database import db
from filters.is_admin import IsAdmin
from keyboards.inline import (
    admin_new_order_kb,
    admin_payment_received_kb,
    admin_complete_kb,
)
from states.states import AdminStates

logger = logging.getLogger(__name__)
router = Router()

ORDER_STATUS_LABELS: dict[str, str] = {
    "new":              "🆕 НОВАЯ",
    "in_work":          "🔄 В РАБОТЕ",
    "waiting_payment":  "⏳ ОЖИДАЕТ ОПЛАТЫ",
    "payment_received": "📸 ОПЛАТА ПОЛУЧЕНА",
    "verifying":        "🔍 ПРОВЕРЯЕТСЯ",
    "completed":        "✅ ЗАВЕРШЕНА",
    "cancelled":        "❌ ОТМЕНЕНА",
}


def _order_text(
    order_id: int, user: object, items: list, total: int,
    status_label: str, created_at: str, extra: str = ""
) -> str:
    username_line = f"@{user['username']}" if user["username"] else "не указан"  # type: ignore[index]
    lines = [
        f"📋 <b>ЗАЯВКА #{order_id}</b>  {status_label}\n",
        f"👤 Имя: {user['name']}",  # type: ignore[index]
        f"📱 Username: {username_line}",
        f"☎️ Телефон: {user['phone']}",  # type: ignore[index]
        f"📧 Email: {user['email']}",  # type: ignore[index]
        "",
        "📚 <b>Состав заказа:</b>",
    ]
    for i, item in enumerate(items, 1):
        lines.append(f"  {i}. {item['course_name']} — {item['price']}₽")
    lines += [
        "",
        f"💰 <b>Итого: {total}₽</b>",
        f"📅 Дата: {created_at}",
    ]
    if extra:
        lines += ["", extra]
    return "\n".join(lines)


async def _edit_all_admin_messages(
    bot: Bot,
    order_id: int,
    text: str,
    keyboard=None,
) -> None:
    """Редактирует все сообщения администраторов по данной заявке."""
    admin_msgs = await db.get_admin_messages(order_id)
    for am in admin_msgs:
        try:
            await bot.edit_message_text(
                text,
                chat_id=am["admin_chat_id"],
                message_id=am["message_id"],
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.warning("Не удалось обновить сообщение у администратора: %s", e)


# ──────────────────── Команда /orders для администратора ──────────────────

@router.message(Command("orders"), IsAdmin())
async def cmd_admin_orders(message: Message) -> None:
    orders = await db.get_all_active_orders()
    if not orders:
        await message.answer("📋 Нет активных заявок.")
        return

    lines = ["📋 <b>Активные заявки:</b>\n"]
    for o in orders:
        status = ORDER_STATUS_LABELS.get(o["status"], o["status"])
        created = o["created_at"][:16].replace("T", " ")
        lines.append(f"• <b>#{o['id']}</b> — {status} ({created})")

    await message.answer("\n".join(lines))


# ─────────────────────── Шаг 1: «В работе» (первый) ──────────────────────

@router.callback_query(F.data.startswith("adm:work1:"), IsAdmin())
async def cb_admin_work1(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    order_id = int(call.data.split(":")[2])
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    if order["status"] != "new":
        await call.answer(
            "Заявка уже обрабатывается или завершена", show_alert=True
        )
        return

    # Занимаем заявку
    await db.set_working_admin(order_id, call.from_user.id)
    await db.update_order_status(order_id, "in_work")

    user = await db.get_user_by_id(order["user_id"])
    items = await db.get_order_items(order_id)
    total = order["total_price"]
    created_at = order["created_at"][:16].replace("T", " ")

    new_text = _order_text(
        order_id, user, items, total,
        ORDER_STATUS_LABELS["in_work"], created_at,
        extra="💬 Введите ссылку на оплату в ответном сообщении:"
    )

    await _edit_all_admin_messages(bot, order_id, new_text, keyboard=None)

    # FSM: ждём ссылку от этого администратора
    await state.set_state(AdminStates.waiting_payment_link)
    await state.update_data(order_id=order_id)

    await call.answer("✅ Заявка взята в работу. Введите ссылку на оплату:")


# ──────────────── Получение ссылки на оплату от администратора ─────────────

@router.message(AdminStates.waiting_payment_link, IsAdmin())
async def receive_payment_link(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    order_id = data.get("order_id")
    await state.clear()

    if not order_id:
        await message.answer("⚠️ Не удалось определить заявку. Попробуйте снова.")
        return

    link = (message.text or "").strip()
    if not link:
        await message.answer("⚠️ Ссылка не может быть пустой.")
        return

    await db.update_order_payment_link(order_id, link)

    order = await db.get_order(order_id)
    user_db = await db.get_user_by_id(order["user_id"])
    items = await db.get_order_items(order_id)
    total = order["total_price"]
    created_at = order["created_at"][:16].replace("T", " ")

    # Обновляем сообщения у всех администраторов
    admin_text = _order_text(
        order_id, user_db, items, total,
        ORDER_STATUS_LABELS["waiting_payment"], created_at,
        extra=f"💳 Ссылка на оплату отправлена клиенту"
    )
    await _edit_all_admin_messages(bot, order_id, admin_text)

    # Отправляем ссылку на оплату клиенту
    from keyboards.inline import payment_done_kb

    telegram_id = user_db["telegram_id"]  # type: ignore[index]
    client_text = (
        f"💳 <b>Ссылка на оплату по заявке #{order_id}</b>\n\n"
        f"🔗 {link}\n\n"
        "После оплаты прикрепите скриншот чека и нажмите кнопку ниже ⬇️"
    )
    await bot.send_message(
        telegram_id, client_text, reply_markup=payment_done_kb(order_id)
    )
    await message.answer(f"✅ Ссылка на оплату отправлена клиенту по заявке #{order_id}.")


# ─────────────── Шаг 2: «В работе» (после получения оплаты) ───────────────

@router.callback_query(F.data.startswith("adm:work2:"), IsAdmin())
async def cb_admin_work2(call: CallbackQuery, bot: Bot) -> None:
    order_id = int(call.data.split(":")[2])
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    if order["status"] != "payment_received":
        await call.answer("Действие недоступно на текущем статусе", show_alert=True)
        return

    await db.update_order_status(order_id, "verifying")

    user_db = await db.get_user_by_id(order["user_id"])
    items = await db.get_order_items(order_id)
    total = order["total_price"]
    created_at = order["created_at"][:16].replace("T", " ")

    admin_text = _order_text(
        order_id, user_db, items, total,
        ORDER_STATUS_LABELS["verifying"], created_at,
        extra=(
            f"🔑 Откройте доступ к курсу(ам) на email: <b>{user_db['email']}</b>\n"  # type: ignore[index]
            "После открытия доступа нажмите кнопку <b>«Завершить»</b>."
        )
    )
    await _edit_all_admin_messages(
        bot, order_id, admin_text, keyboard=admin_complete_kb(order_id)
    )
    await call.answer("✅ Статус обновлён — проверяется")


# ─────────────────────────── «Завершить» ──────────────────────────────────

@router.callback_query(F.data.startswith("adm:complete:"), IsAdmin())
async def cb_admin_complete(call: CallbackQuery, bot: Bot) -> None:
    order_id = int(call.data.split(":")[2])
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    if order["status"] != "verifying":
        await call.answer("Действие недоступно на текущем статусе", show_alert=True)
        return

    await db.update_order_status(order_id, "completed")

    user_db = await db.get_user_by_id(order["user_id"])
    items = await db.get_order_items(order_id)
    total = order["total_price"]
    created_at = order["created_at"][:16].replace("T", " ")

    # Выдаём доступы клиенту в БД
    for item in items:
        await db.grant_access(
            user_db_id=user_db["id"],  # type: ignore[index]
            course_id=item["course_id"],
            course_name=item["course_name"],
            course_link=item["course_link"],
            order_id=order_id,
        )

    # Финальное сообщение администратору
    admin_text = _order_text(
        order_id, user_db, items, total,
        ORDER_STATUS_LABELS["completed"], created_at,
        extra="✅ Доступ открыт, клиент уведомлён."
    )
    await _edit_all_admin_messages(bot, order_id, admin_text, keyboard=None)

    # Уведомление клиенту с ссылками на курсы
    email = user_db["email"]  # type: ignore[index]
    telegram_id = user_db["telegram_id"]  # type: ignore[index]

    client_lines = [
        f"🎉 <b>Заявка #{order_id} выполнена!</b>\n",
        f"Доступ открыт на электронную почту <b>{email}</b>\n",
        "📚 <b>Ваши курсы:</b>",
    ]
    for i, item in enumerate(items, 1):
        client_lines.append(
            f"\n{i}. 🎓 <b>{item['course_name']}</b>\n"
            f"   🔗 <a href=\"{item['course_link']}\">Перейти к курсу</a>"
        )
    client_lines.append(
        "\n\n📂 Все доступы также доступны в разделе <b>🔓 Открытые доступы</b>."
    )

    await bot.send_message(
        telegram_id,
        "\n".join(client_lines),
        disable_web_page_preview=True,
    )
    await call.answer("✅ Заявка завершена!")


# ──────────────────────────── «Отклонить» ─────────────────────────────────

@router.callback_query(F.data.startswith("adm:reject:"), IsAdmin())
async def cb_admin_reject(call: CallbackQuery, bot: Bot) -> None:
    order_id = int(call.data.split(":")[2])
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    if order["status"] not in ("new", "in_work"):
        await call.answer("Нельзя отклонить заявку на этом этапе", show_alert=True)
        return

    await db.update_order_status(order_id, "cancelled")

    user_db = await db.get_user_by_id(order["user_id"])
    items = await db.get_order_items(order_id)
    total = order["total_price"]
    created_at = order["created_at"][:16].replace("T", " ")

    admin_text = _order_text(
        order_id, user_db, items, total,
        ORDER_STATUS_LABELS["cancelled"], created_at
    )
    await _edit_all_admin_messages(bot, order_id, admin_text, keyboard=None)

    # Уведомляем клиента
    telegram_id = user_db["telegram_id"]  # type: ignore[index]
    await bot.send_message(
        telegram_id,
        f"❌ <b>Заявка #{order_id} отклонена.</b>\n\n"
        "Если у вас есть вопросы — обратитесь в поддержку через раздел <b>❓ Помощь</b>."
    )
    await call.answer("Заявка отклонена")
