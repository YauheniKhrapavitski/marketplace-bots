from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.feedback import Feedback
from app.integrations.wildberries.schemas import Feedback as WbFeedback


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_from_wb(self, account_id: int, item: WbFeedback) -> tuple[Feedback, bool]:
        existing = await self.get_by_wb_id(account_id, item.id)
        if existing:
            existing.rating = item.rating
            existing.review_text = item.text
            existing.pros = item.pros
            existing.cons = item.cons
            existing.raw_payload = item.raw
            return existing, False
        feedback = Feedback(
            wb_account_id=account_id,
            wb_feedback_id=item.id,
            nm_id=item.nm_id,
            product_name=item.product_name,
            supplier_article=item.supplier_article,
            buyer_name=item.buyer_name,
            rating=item.rating,
            review_text=item.text,
            pros=item.pros,
            cons=item.cons,
            created_at_wb=item.created_at,
            raw_payload=item.raw,
            status="new",
        )
        self._session.add(feedback)
        await self._session.flush()
        return feedback, True

    async def get_by_wb_id(self, account_id: int, wb_feedback_id: str) -> Feedback | None:
        result = await self._session.scalar(
            select(Feedback).where(
                Feedback.wb_account_id == account_id,
                Feedback.wb_feedback_id == wb_feedback_id,
            )
        )
        return cast("Feedback | None", result)

    async def get(self, feedback_id: int) -> Feedback | None:
        return await self._session.get(Feedback, feedback_id)

    async def next_pending(self) -> Feedback | None:
        now = datetime.now(UTC)
        stmt: Select[tuple[Feedback]] = (
            select(Feedback)
            .where(
                Feedback.status.in_(["new", "pending", "failed", "postponed"]),
                (Feedback.postponed_until.is_(None)) | (Feedback.postponed_until <= now),
            )
            .order_by(Feedback.created_at.asc())
            .limit(1)
        )
        return cast("Feedback | None", await self._session.scalar(stmt))

    async def count_queue(self) -> int:
        now = datetime.now(UTC)
        value = await self._session.scalar(
            select(func.count(Feedback.id)).where(
                Feedback.status.in_(["new", "pending", "failed", "postponed"]),
                (Feedback.postponed_until.is_(None)) | (Feedback.postponed_until <= now),
            )
        )
        return int(value or 0)

    async def count_answered_since(self, since: datetime) -> int:
        value = await self._session.scalar(
            select(func.count(Feedback.id)).where(
                Feedback.status == "answered",
                Feedback.answer_sent_at >= since,
            )
        )
        return int(value or 0)

    async def restore_sending(self) -> int:
        result = await self._session.scalars(select(Feedback).where(Feedback.status == "sending"))
        count = 0
        for feedback in result.all():
            feedback.status = "pending"
            count += 1
        return count

    @staticmethod
    def postpone_until(hours: int) -> datetime:
        return datetime.now(UTC) + timedelta(hours=hours)
