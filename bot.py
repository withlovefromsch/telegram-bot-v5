"""Точка входа бота «Курсы на миллион 💸💵»."""
import os
import sys

# Добавляем корень проекта в sys.path, чтобы при запуске из сервиса
# импорты вида `from data.courses import ...` работали корректно.
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

# Также добавляем /app (на сервере может запускаться из другой директории)
if '/app' not in sys.path:
    sys.path.insert(0, '/app')

    # Диагностика: показываем sys.path и содержимое /app в логах контейнера
    try:
        print("=== DIAG: bot startup ===")
        print("DIAG: project_root=", project_root)
        print("DIAG: cwd=", os.getcwd())
        print("DIAG: PYTHONPATH=", os.environ.get('PYTHONPATH'))
        print("DIAG: DATA_DIR=", os.environ.get('DATA_DIR'))
        print("DIAG: sys.path=", sys.path)
        try:
            print("DIAG: list /app=", sorted(os.listdir('/app')))
        except Exception as e:
            print("DIAG: cannot list /app:", e)
        try:
            print("DIAG: list project_root=", sorted(os.listdir(project_root)))
        except Exception as e:
            print("DIAG: cannot list project_root:", e)
        print("=== DIAG end ===")
    except Exception:
        pass
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import BOT_TOKEN, ADMIN_IDS
from database.db import init_db
from handlers import registration, profile, courses, orders, help, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH: str = os.getenv('DATA_DIR', '/app/data') + '/bot_database.db'


async def set_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="🚀 Запустить / перезапустить бота"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

    # Команды только для администраторов (scope AllPrivateChats не ограничивает,
    # поэтому для продакшена можно добавить BotCommandScopeChat)
    admin_commands = [
        BotCommand(command="start",  description="🚀 Запустить бота"),
        BotCommand(command="orders", description="📋 Активные заявки"),
    ]
    for admin_id in ADMIN_IDS:
        try:
            from aiogram.types import BotCommandScopeChat
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except Exception:
            pass


async def set_bot_info(bot: Bot) -> None:
    try:
        await bot.set_my_description(
            "🎓 Бот магазина курсов «Курсы на миллион 💸💵»\n\n"
            "Здесь вы найдёте лучшие курсы по AI, нейросетям и автоматизации.\n\n"
            "Нажмите ЗАПУСТИТЬ, чтобы начать!"
        )
        await bot.set_my_short_description(
            "Магазин курсов по AI и нейросетям 🤖💸"
        )
    except Exception as e:
        logger.warning("Не удалось установить описание бота: %s", e)


async def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан! Заполните файл .env")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важен: admin-router раньше остальных, registration — самый первый
    dp.include_router(registration.router)
    dp.include_router(admin.router)
    dp.include_router(profile.router)
    dp.include_router(courses.router)
    dp.include_router(orders.router)
    dp.include_router(help.router)

    await init_db()
    logger.info("✅ База данных инициализирована")

    await set_bot_commands(bot)
    await set_bot_info(bot)
    logger.info("🤖 Бот запущен")

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
