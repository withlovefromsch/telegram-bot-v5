from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery

from config import ADMIN_IDS


class IsAdmin(Filter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user.id in ADMIN_IDS
