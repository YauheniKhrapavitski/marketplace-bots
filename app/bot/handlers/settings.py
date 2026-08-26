from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_settings

router = Router()


@router.message(Command("settings"))
async def settings(message: Message) -> None:
    app_settings = get_settings()
    await message.answer(
        "Настройки\n"
        f"Интервал проверки: {app_settings.sync_interval_minutes} мин.\n"
        f"Режим Wildberries: {app_settings.wb_environment}\n"
        f"Минимальная длина ответа: контролируется шаблонами\n"
        f"Бренд: {app_settings.brand_name or 'не указан'}\n"
        "Для замены WB API-токена задайте переменную WB_API_TOKEN и перезапустите приложение."
    )
