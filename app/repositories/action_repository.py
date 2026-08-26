from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.action import FeedbackAction


class ActionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        feedback_id: int,
        action: str,
        old_status: str | None,
        new_status: str | None,
        telegram_user_id: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> FeedbackAction:
        item = FeedbackAction(
            feedback_id=feedback_id,
            telegram_user_id=telegram_user_id,
            action=action,
            old_status=old_status,
            new_status=new_status,
            payload=payload or {},
        )
        self._session.add(item)
        return item

    async def has_action(self, feedback_id: int, action: str) -> bool:
        found = await self._session.scalar(
            select(FeedbackAction.id)
            .where(FeedbackAction.feedback_id == feedback_id, FeedbackAction.action == action)
            .limit(1)
        )
        return found is not None
