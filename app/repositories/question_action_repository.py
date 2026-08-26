from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.question import QuestionAction


class QuestionActionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        question_id: int,
        action: str,
        old_status: str | None,
        new_status: str | None,
        telegram_user_id: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> QuestionAction:
        item = QuestionAction(
            question_id=question_id,
            telegram_user_id=telegram_user_id,
            action=action,
            old_status=old_status,
            new_status=new_status,
            payload=payload or {},
        )
        self._session.add(item)
        return item

    async def has_action(self, question_id: int, action: str) -> bool:
        found = await self._session.scalar(
            select(QuestionAction.id)
            .where(QuestionAction.question_id == question_id, QuestionAction.action == action)
            .limit(1)
        )
        return found is not None
