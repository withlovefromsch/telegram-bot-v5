"""Все инлайн-клавиатуры бота."""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from data.courses import COURSES


# ─────────────────────────── Курсы ────────────────────────────────────────

def courses_list_kb(cart: list[int]) -> InlineKeyboardMarkup:
    """Список курсов. Иконка корзины в одной строке с названием курса."""
    buttons: list[list[InlineKeyboardButton]] = []
    for cid, c in COURSES.items():
        in_cart = cid in cart
        icon = "✅" if in_cart else "🛒"
        buttons.append([
            InlineKeyboardButton(
                text=f"{c['emoji']} {c['name']} — {c['price']}₽",
                callback_data=f"course_info:{cid}",
            ),
            InlineKeyboardButton(
                text=icon,
                callback_data=f"cart:{'remove' if in_cart else 'add'}:{cid}",
            ),
        ])

    if cart:
        buttons.append([
            InlineKeyboardButton(
                text=f"🛒 Перейти в корзину ({len(cart)})",
                callback_data="open_cart",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def course_detail_kb(course_id: int, in_cart: bool) -> InlineKeyboardMarkup:
    icon = "✅" if in_cart else "🛒"
    label = "Убрать из корзины" if in_cart else "В корзину"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{icon} {label}",
            callback_data=f"cart:{'remove' if in_cart else 'add'}:{course_id}",
        )],
        [InlineKeyboardButton(text="◀️ Назад к курсам", callback_data="courses_list")],
    ])


# ─────────────────────────── Корзина ──────────────────────────────────────

def cart_kb(cart: list[int]) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for cid in cart:
        course = COURSES.get(cid)
        if course:
            name_short = course["name"][:35] + ("…" if len(course["name"]) > 35 else "")
            buttons.append([
                InlineKeyboardButton(
                    text=f"❌ {name_short}",
                    callback_data=f"cart:remove:{cid}",
                )
            ])
    buttons.append([
        InlineKeyboardButton(text="📋 Оформить заявку", callback_data="create_order"),
        InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart"),
    ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад к курсам", callback_data="courses_list"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─────────────────────────── Заказы (клиент) ──────────────────────────────

def order_confirm_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Отправить заявку",
            callback_data=f"order:confirm:{order_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"order:cancel:{order_id}",
        ),
    ]])


def order_status_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🔄 Обновить статус",
            callback_data=f"order:status:{order_id}",
        ),
    ]])


def payment_done_kb(order_id: int) -> InlineKeyboardMarkup:
    """Кнопка «Оплачено» под ссылкой на оплату."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Оплачено",
            callback_data=f"paid:{order_id}",
        ),
    ]])


# ─────────────────────────── Заказы (админ) ───────────────────────────────

def admin_new_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ В работе",
            callback_data=f"adm:work1:{order_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"adm:reject:{order_id}",
        ),
    ]])


def admin_payment_received_kb(order_id: int) -> InlineKeyboardMarkup:
    """После получения скриншота оплаты."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ В работе",
            callback_data=f"adm:work2:{order_id}",
        ),
    ]])


def admin_complete_kb(order_id: int) -> InlineKeyboardMarkup:
    """Финальная кнопка завершения заявки."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Завершить",
            callback_data=f"adm:complete:{order_id}",
        ),
    ]])
