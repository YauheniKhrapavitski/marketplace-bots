from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from app.db.models.action import FeedbackAction
from app.db.session import SessionFactory

router = Router()


@router.message(Command("history"))
async def history(message: Message) -> None:
    async with SessionFactory() as session:
        result = await session.scalars(
            select(FeedbackAction).order_by(FeedbackAction.created_at.desc()).limit(20)
        )
        actions = result.all()
    if not actions:
        await message.answer("История пока пуста")
        return
    await message.answer(
        "\n".join(
            f"{item.created_at:%Y-%m-%d %H:%M} feedback={item.feedback_id} "
            f"{item.action}: {item.old_status}->{item.new_status}"
            for item in actions
        )
    )
