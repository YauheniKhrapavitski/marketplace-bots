from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ozon import OzonReviewAction


class OzonReviewActionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        review_id: int,
        action: str,
        old_status: str | None,
        new_status: str | None,
        telegram_user_id: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> OzonReviewAction:
        item = OzonReviewAction(
            review_id=review_id,
            telegram_user_id=telegram_user_id,
            action=action,
            old_status=old_status,
            new_status=new_status,
            payload=payload or {},
        )
        self._session.add(item)
        return item

    async def has_action(self, review_id: int, action: str) -> bool:
        found = await self._session.scalar(
            select(OzonReviewAction.id)
            .where(OzonReviewAction.review_id == review_id, OzonReviewAction.action == action)
            .limit(1)
        )
        return found is not None
