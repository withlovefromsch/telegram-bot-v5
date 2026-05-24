"""Каталог курсов + управление корзиной."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

try:
    from data.courses import COURSES
except ModuleNotFoundError:
    # Fallback: try loading the module directly from common locations inside the container
    import importlib.util
    import os

    COURSES = {}
    candidates = [
        "/srv/app/data/courses.py",
        "/app/data/courses.py",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "courses.py"),
    ]
    for path in candidates:
        try:
            if path and os.path.exists(path):
                spec = importlib.util.spec_from_file_location("data.courses", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                COURSES = getattr(mod, "COURSES", {})
                break
        except Exception:
            continue
    if not COURSES:
        raise
from database import db
from keyboards.inline import (
    courses_list_kb,
    course_detail_kb,
    cart_kb,
    order_confirm_kb,
)

router = Router()


# ────────────────────────── Список курсов ─────────────────────────────────

async def _render_courses(event: Message | CallbackQuery, cart: list[int]) -> None:
    text = (
        "📚 <b>Список курсов</b>\n\n"
        "Нажмите на название курса, чтобы узнать подробнее.\n"
        "Добавляйте понравившиеся в корзину 🛒"
    )
    kb = courses_list_kb(cart)

    if isinstance(event, Message):
        await event.answer(text, reply_markup=kb)
    else:
        await event.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]


@router.message(F.text == "📚 Список курсов")
async def show_courses(message: Message) -> None:
    user = await db.get_user(message.from_user.id)  # type: ignore[arg-type]
    if not user:
        await message.answer("⚠️ Вы не зарегистрированы. Нажмите /start")
        return
    cart = await db.get_cart(user["id"])
    await _render_courses(message, cart)


@router.callback_query(F.data == "courses_list")
async def cb_courses_list(call: CallbackQuery) -> None:
    user = await db.get_user(call.from_user.id)
    if not user:
        await call.answer("Сначала зарегистрируйтесь /start", show_alert=True)
        return
    cart = await db.get_cart(user["id"])
    await _render_courses(call, cart)
    await call.answer()


# ──────────────────────── Детальная страница курса ────────────────────────

@router.callback_query(F.data.startswith("course_info:"))
async def cb_course_info(call: CallbackQuery) -> None:
    course_id = int(call.data.split(":")[1])
    course = COURSES.get(course_id)
    if not course:
        await call.answer("Курс не найден", show_alert=True)
        return

    user = await db.get_user(call.from_user.id)
    if not user:
        await call.answer("Сначала зарегистрируйтесь /start", show_alert=True)
        return

    cart = await db.get_cart(user["id"])
    in_cart = course_id in cart

    text = (
        f"{course['emoji']} <b>{course['name']}</b>\n\n"
        f"💰 <b>Цена:</b> {course['price']}₽\n\n"
        f"📝 <b>Описание:</b>\n{course['description']}"
    )
    await call.message.edit_text(  # type: ignore[union-attr]
        text, reply_markup=course_detail_kb(course_id, in_cart)
    )
    await call.answer()


# ─────────────────────── Добавление / удаление из корзины ─────────────────

@router.callback_query(F.data.startswith("cart:"))
async def cb_cart_action(call: CallbackQuery) -> None:
    _, action, cid_str = call.data.split(":")
    course_id = int(cid_str)

    user = await db.get_user(call.from_user.id)
    if not user:
        await call.answer("Сначала зарегистрируйтесь /start", show_alert=True)
        return

    if action == "add":
        added = await db.add_to_cart(user["id"], course_id)
        if added:
            await call.answer("✅ Курс добавлен в корзину!")
        else:
            await call.answer("Курс уже в корзине")
    elif action == "remove":
        await db.remove_from_cart(user["id"], course_id)
        await call.answer("❌ Курс удалён из корзины")

    # Обновляем клавиатуру текущего экрана
    cart = await db.get_cart(user["id"])
    current_text = call.message.text or ""  # type: ignore[union-attr]

    # Определяем — мы на странице курса или в списке?
    if "Список курсов" in current_text or "Нажмите на название" in current_text:
        await call.message.edit_reply_markup(  # type: ignore[union-attr]
            reply_markup=courses_list_kb(cart)
        )
    else:
        in_cart = course_id in cart
        await call.message.edit_reply_markup(  # type: ignore[union-attr]
            reply_markup=course_detail_kb(course_id, in_cart)
        )


# ────────────────────────── Просмотр корзины ──────────────────────────────

@router.callback_query(F.data == "open_cart")
async def cb_open_cart(call: CallbackQuery) -> None:
    user = await db.get_user(call.from_user.id)
    if not user:
        await call.answer("Сначала зарегистрируйтесь /start", show_alert=True)
        return
    await _show_cart(call)
    await call.answer()


async def _show_cart(call: CallbackQuery) -> None:
    user = await db.get_user(call.from_user.id)
    cart = await db.get_cart(user["id"])  # type: ignore[index]

    if not cart:
        await call.message.edit_text(  # type: ignore[union-attr]
            "🛒 Ваша корзина пуста.\n\nДобавьте курсы из каталога.",
            reply_markup=courses_list_kb([]),
        )
        return

    lines = ["🛒 <b>Ваша корзина:</b>\n"]
    total = 0
    for cid in cart:
        c = COURSES.get(cid)
        if c:
            lines.append(f"• {c['emoji']} {c['name']} — {c['price']}₽")
            total += c["price"]
    lines.append(f"\n💰 <b>Итого: {total}₽</b>")
    lines.append("\nНажмите ❌ рядом с курсом, чтобы убрать его.")

    await call.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines), reply_markup=cart_kb(cart)
    )


@router.callback_query(F.data == "clear_cart")
async def cb_clear_cart(call: CallbackQuery) -> None:
    user = await db.get_user(call.from_user.id)
    if not user:
        await call.answer()
        return
    await db.clear_cart(user["id"])
    await call.answer("🗑 Корзина очищена")
    cart = await db.get_cart(user["id"])
    await call.message.edit_text(  # type: ignore[union-attr]
        "🛒 Корзина очищена. Выберите курсы из каталога.",
        reply_markup=courses_list_kb(cart),
    )


# ─────────────────────────── Оформление заявки ────────────────────────────

@router.callback_query(F.data == "create_order")
async def cb_create_order(call: CallbackQuery) -> None:
    user = await db.get_user(call.from_user.id)
    if not user:
        await call.answer("Сначала зарегистрируйтесь /start", show_alert=True)
        return

    cart = await db.get_cart(user["id"])
    if not cart:
        await call.answer("Корзина пуста", show_alert=True)
        return

    # Создаём предварительный заказ
    total = sum(COURSES[cid]["price"] for cid in cart if cid in COURSES)
    order_id = await db.create_order(user["id"], total)
    for cid in cart:
        c = COURSES.get(cid)
        if c:
            await db.add_order_item(order_id, cid, c["name"], c["price"], c["link"])

    # Формируем текст подтверждения
    lines = [f"📋 <b>Подтверждение заявки #{order_id}</b>\n"]
    lines.append(f"👤 Имя: {user['name']}")
    lines.append(f"📧 Email: {user['email']}\n")
    lines.append("📚 <b>Состав заказа:</b>")
    for i, cid in enumerate(cart, 1):
        c = COURSES.get(cid)
        if c:
            lines.append(f"  {i}. {c['emoji']} {c['name']} — {c['price']}₽")
    lines.append(f"\n💰 <b>Итого: {total}₽</b>")
    lines.append("\nОтправить заявку менеджеру?")

    await call.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines), reply_markup=order_confirm_kb(order_id)
    )
    await call.answer()
