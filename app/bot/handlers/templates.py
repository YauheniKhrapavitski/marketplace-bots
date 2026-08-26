from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.db.session import SessionFactory
from app.repositories.template_repository import TemplateRepository
from app.services.template_catalog import STARTER_TEMPLATES

router = Router()


@router.message(Command("templates"))
async def templates(message: Message) -> None:
    async with SessionFactory() as session:
        repo = TemplateRepository(session)
        candidates = await repo.list_active_candidates()
        if not candidates:
            await repo.seed(STARTER_TEMPLATES)
            await session.commit()
            candidates = await repo.list_active_candidates()
    lines = ["Шаблоны:"]
    lines.extend(f"{item.code}: {item.name} ({item.category})" for item in candidates)
    await message.answer("\n".join(lines))
