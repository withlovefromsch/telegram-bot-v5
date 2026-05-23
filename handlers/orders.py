"""Обработчики заявок на стороне клиента."""
from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADMIN_IDS
from database import db
from keyboards.inline import (
    order_status_kb,
    payment_done_kb,
    admin_new_order_kb,
)
from keyboards.inline import courses_list_kb
from states.states import OrderStates

logger = logging.getLogger(__name__)
router = Router()

ORDER_STATUS_MAP = {
    "new":              "🆕 Новая — ожидает рассмотрения",
    "in_work":          "🔄 В работе у менеджера",
    "waiting_payment":  "💳 Ожидает оплаты — проверьте сообщение со ссылкой",
    "payment_received": "📸 Оплата получена — менеджер проверяет",
    "verifying":        "🔍 Проверяется менеджером",
    "completed":        "✅ Завершена — доступ открыт",
    "cancelled":        "❌ Отменена",
}


def _format_order_for_admin(
    order_id: int,
    user: object,
    items: list,
    total: int,
    status_label: str,
    created_at: str,
) -> str:
    """Форматирует текст заявки для отправки/редактирования в чате администратора."""
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
    return "\n".join(lines)


# ──────────────────────── Подтверждение заявки ────────────────────────────

@router.callback_query(F.data.startswith("order:confirm:"))
async def cb_confirm_order(call: CallbackQuery, bot: Bot) -> None:
    order_id = int(call.data.split(":")[2])
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    user = await db.get_user_by_id(order["user_id"])
    if not user:
        await call.answer()
        return

    items = await db.get_order_items(order_id)
    total = order["total_price"]
    created_at = order["created_at"][:16].replace("T", " ")

    admin_text = _format_order_for_admin(
        order_id, user, items, total, "🆕 НОВАЯ", created_at
    )

    # Очищаем корзину
    await db.clear_cart(user["id"])

    # Отправляем всем администраторам
    for admin_id in ADMIN_IDS:
        try:
            msg = await bot.send_message(
                admin_id, admin_text, reply_markup=admin_new_order_kb(order_id)
            )
            await db.save_admin_message(order_id, admin_id, msg.message_id)
        except Exception as e:
            logger.warning("Не удалось отправить заявку администратору %s: %s", admin_id, e)

    # Обновляем статус заказа
    await db.update_order_status(order_id, "new")

    # Уведомляем клиента
    await call.message.edit_text(  # type: ignore[union-attr]
        f"✅ <b>Заявка #{order_id} успешно отправлена!</b>\n\n"
        f"Менеджер свяжется с вами в ближайшее время.\n\n"
        f"Отслеживайте статус заявки ниже 👇",
        reply_markup=order_status_kb(order_id),
    )
    await call.answer("Заявка отправлена!")


@router.callback_query(F.data.startswith("order:cancel:"))
async def cb_cancel_order(call: CallbackQuery) -> None:
    order_id = int(call.data.split(":")[2])
    await db.update_order_status(order_id, "cancelled")
    user = await db.get_user(call.from_user.id)
    cart: list[int] = []
    if user:
        cart = await db.get_cart(user["id"])
    await call.message.edit_text(  # type: ignore[union-attr]
        "❌ Заявка отменена. Вернитесь в каталог, чтобы добавить курсы.",
        reply_markup=courses_list_kb(cart),
    )
    await call.answer("Заявка отменена")


# ──────────────────────── Проверка статуса ────────────────────────────────

@router.callback_query(F.data.startswith("order:status:"))
async def cb_order_status(call: CallbackQuery) -> None:
    order_id = int(call.data.split(":")[2])
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заявка не найдена", show_alert=True)
        return
    status_label = ORDER_STATUS_MAP.get(order["status"], order["status"])
    await call.answer(f"Статус заявки #{order_id}:\n{status_label}", show_alert=True)


# ──────────────────────── «Оплачено» + скриншот ───────────────────────────

@router.callback_query(F.data.startswith("paid:"))
async def cb_paid(call: CallbackQuery, state: FSMContext) -> None:
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order["status"] != "waiting_payment":
        await call.answer(
            "Действие недоступно на текущем статусе заявки", show_alert=True
        )
        return

    await state.set_state(OrderStates.waiting_payment_screenshot)
    await state.update_data(order_id=order_id)

    await call.message.answer(  # type: ignore[union-attr]
        "📸 Пришлите скриншот (фото) чека об оплате.\n\n"
        "После отправки менеджер проверит платёж и откроет вам доступ к курсам."
    )
    await call.answer()


@router.message(OrderStates.waiting_payment_screenshot, F.photo)
async def receive_screenshot(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    order_id = data.get("order_id")
    await state.clear()

    if not order_id:
        await message.answer("⚠️ Что-то пошло не так. Попробуйте снова.")
        return

    order = await db.get_order(order_id)
    if not order:
        await message.answer("⚠️ Заявка не найдена.")
        return

    photo_id = message.photo[-1].file_id  # type: ignore[index]
    await db.update_order_screenshot(order_id, photo_id)

    # Уведомляем клиента
    await message.answer(
        f"✅ Скриншот оплаты по заявке <b>#{order_id}</b> получен!\n\n"
        "Менеджер проверит платёж и откроет доступ к курсам.\n\n"
        "Отслеживайте статус:",
        reply_markup=order_status_kb(order_id),
    )

    # Пересылаем скриншот и уведомляем администратора
    from keyboards.inline import admin_payment_received_kb

    user = await db.get_user(message.from_user.id)  # type: ignore[arg-type]
    caption = (
        f"📸 <b>Скриншот оплаты по заявке #{order_id}</b>\n"
        f"Клиент: {user['name'] if user else 'неизвестен'}"
    )
    admin_msgs = await db.get_admin_messages(order_id)
    for am in admin_msgs:
        try:
            await bot.send_photo(
                am["admin_chat_id"],
                photo=photo_id,
                caption=caption,
            )
            # Редактируем оригинальное сообщение с заявкой
            order_upd = await db.get_order(order_id)
            user_db = await db.get_user_by_id(order_upd["user_id"])
            items = await db.get_order_items(order_id)
            total = order_upd["total_price"]
            created_at = order_upd["created_at"][:16].replace("T", " ")
            new_text = _format_order_for_admin(
                order_id, user_db, items, total,
                "📸 ОПЛАТА ПОЛУЧЕНА", created_at
            ) + "\n\n✅ Скриншот чека прикреплён выше ☝️"
            await bot.edit_message_text(
                new_text,
                chat_id=am["admin_chat_id"],
                message_id=am["message_id"],
                reply_markup=admin_payment_received_kb(order_id),
            )
        except Exception as e:
            logger.warning("Не удалось обновить сообщение у администратора: %s", e)


@router.message(OrderStates.waiting_payment_screenshot)
async def screenshot_not_photo(message: Message) -> None:
    await message.answer("⚠️ Пожалуйста, пришлите <b>фото</b> скриншота чека об оплате.")


# ────────────────────── Открытые доступы (клиент) ─────────────────────────

@router.message(F.text == "🔓 Открытые доступы")
async def show_accesses(message: Message) -> None:
    user = await db.get_user(message.from_user.id)  # type: ignore[arg-type]
    if not user:
        await message.answer("⚠️ Вы не зарегистрированы. Нажмите /start")
        return

    accesses = await db.get_user_accesses(user["id"])
    if not accesses:
        await message.answer(
            "🔓 <b>Открытые доступы</b>\n\n"
            "У вас пока нет купленных курсов.\n\n"
            "Перейдите в раздел <b>📚 Список курсов</b>, чтобы выбрать курс."
        )
        return

    lines = ["🔓 <b>Открытые доступы</b>\n"]
    for i, acc in enumerate(accesses, 1):
        date = acc["granted_at"][:10]
        lines.append(
            f"{i}. 🎓 <b>{acc['course_name']}</b>\n"
            f"   📅 Доступ открыт: {date}\n"
            f"   🔗 <a href=\"{acc['course_link']}\">Перейти к курсу</a>\n"
        )

    await message.answer("\n".join(lines), disable_web_page_preview=True)
