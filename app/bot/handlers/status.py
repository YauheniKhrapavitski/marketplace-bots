from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_settings
from app.db.session import SessionFactory
from app.repositories.account_repository import AccountRepository
from app.repositories.feedback_repository import FeedbackRepository

router = Router()


@router.message(Command("status"))
async def status(message: Message) -> None:
    settings = get_settings()
    async with SessionFactory() as session:
        account = await AccountRepository(session).get_active()
        feedbacks = FeedbackRepository(session)
        queue_count = await feedbacks.count_queue()
        answered_today = await feedbacks.count_answered_since(
            datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        )
        last_sync = (
            account.last_successful_sync_at.isoformat()
            if account and account.last_successful_sync_at
            else "нет"
        )
        last_error = account.last_sync_error if account and account.last_sync_error else "нет"
    await message.answer(
        "Статус\n"
        f"Wildberries подключён: {'да' if account else 'нет'}\n"
        f"Режим: {settings.wb_environment}\n"
        f"Последняя успешная синхронизация: {last_sync}\n"
        f"Новых отзывов: {queue_count}\n"
        f"Очередь: {queue_count}\n"
        f"Ответов за сутки: {answered_today}\n"
        f"Последняя ошибка: {last_error}"
    )
