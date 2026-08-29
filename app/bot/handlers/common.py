from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer(
        "Ассистент помогает обрабатывать отзывы Wildberries. Он получает новые отзывы, "
        "подбирает ответ из шаблонов и отправляет его после вашего подтверждения"
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "/start - главное меню\n"
        "/status - состояние интеграции\n"
        "/reviews - следующий отзыв\n"
        "/sync - ручная синхронизация\n"
        "/process_reviews - обработать накопившиеся отзывы\n"
        "/templates - управление шаблонами\n"
        "/settings - настройки\n"
        "/history - последние операции"
    )
