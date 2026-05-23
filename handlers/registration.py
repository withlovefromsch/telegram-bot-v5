"""Регистрация нового пользователя."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import db
from keyboards.reply import main_menu_kb, phone_kb, cancel_kb
from states.states import RegistrationStates

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(message.from_user.id)  # type: ignore[arg-type]
    if user:
        await message.answer(
            f"👋 С возвращением, <b>{user['name']}</b>!\n\n"
            "Выберите нужный раздел:",
            reply_markup=main_menu_kb(),
        )
        return

    await message.answer(
        "🎓 Добро пожаловать в <b>Курсы на миллион 💸💵</b>!\n\n"
        "Здесь вы найдёте лучшие курсы по AI, нейросетям и автоматизации.\n\n"
        "Для начала работы пройдите быструю регистрацию.\n\n"
        "📝 Введите ваше <b>имя</b>:",
    )
    await state.set_state(RegistrationStates.waiting_name)


# ──────────────────────────── Шаг 1: Имя ──────────────────────────────────

@router.message(RegistrationStates.waiting_name)
async def reg_name(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Регистрация отменена. Нажмите /start чтобы начать снова.")
        return

    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("❌ Имя слишком короткое. Введите минимум 2 символа:")
        return

    await state.update_data(name=name)
    await message.answer(
        f"✅ Отлично, <b>{name}</b>!\n\n"
        "Поделитесь вашим <b>номером телефона</b>, нажав кнопку ниже:",
        reply_markup=phone_kb(),
    )
    await state.set_state(RegistrationStates.waiting_phone)


# ──────────────────────────── Шаг 2: Телефон ──────────────────────────────

@router.message(RegistrationStates.waiting_phone, F.contact)
async def reg_phone(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number  # type: ignore[union-attr]
    await state.update_data(phone=phone)
    await message.answer(
        "✅ Номер телефона сохранён!\n\n"
        "📧 Введите вашу <b>электронную почту</b> — на неё будет открыт доступ к курсам:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(RegistrationStates.waiting_email)


@router.message(RegistrationStates.waiting_phone)
async def reg_phone_text(message: Message) -> None:
    await message.answer(
        "⚠️ Пожалуйста, используйте кнопку для отправки номера телефона 👇",
        reply_markup=phone_kb(),
    )


# ──────────────────────────── Шаг 3: Email ────────────────────────────────

@router.message(RegistrationStates.waiting_email)
async def reg_email(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Регистрация отменена. Нажмите /start чтобы начать снова.")
        return

    email = (message.text or "").strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        await message.answer(
            "❌ Некорректный email. Введите правильный адрес (например: example@mail.ru):"
        )
        return

    data = await state.get_data()
    username = message.from_user.username or ""  # type: ignore[union-attr]

    await db.create_user(
        telegram_id=message.from_user.id,  # type: ignore[union-attr]
        username=username,
        name=data["name"],
        phone=data["phone"],
        email=email,
    )
    await state.clear()

    await message.answer(
        "🎉 <b>Регистрация завершена!</b>\n\n"
        f"👤 Имя: {data['name']}\n"
        f"📱 Телефон: {data['phone']}\n"
        f"📧 Email: {email}\n\n"
        "Добро пожаловать! Выберите нужный раздел 👇",
        reply_markup=main_menu_kb(),
    )
