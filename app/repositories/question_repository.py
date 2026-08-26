from datetime import UTC, datetime
from typing import cast

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.question import Question
from app.integrations.wildberries.question_schemas import Question as WbQuestion


class QuestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_from_wb(self, account_id: int, item: WbQuestion) -> tuple[Question, bool]:
        existing = await self.get_by_wb_id(account_id, item.id)
        if existing:
            existing.question_text = item.text
            existing.was_viewed = item.was_viewed
            existing.is_warned = item.is_warned
            existing.state = item.state
            existing.raw_payload = item.raw
            return existing, False
        question = Question(
            wb_account_id=account_id,
            wb_question_id=item.id,
            nm_id=item.nm_id,
            imt_id=item.imt_id,
            product_name=item.product_name,
            supplier_article=item.supplier_article,
            brand_name=item.brand_name,
            question_text=item.text,
            state=item.state,
            created_at_wb=item.created_at,
            was_viewed=item.was_viewed,
            is_warned=item.is_warned,
            raw_payload=item.raw,
            status="new",
        )
        self._session.add(question)
        await self._session.flush()
        return question, True

    async def get_by_wb_id(self, account_id: int, wb_question_id: str) -> Question | None:
        result = await self._session.scalar(
            select(Question).where(
                Question.wb_account_id == account_id,
                Question.wb_question_id == wb_question_id,
            )
        )
        return cast("Question | None", result)

    async def get(self, question_id: int) -> Question | None:
        return await self._session.get(Question, question_id)

    async def next_pending(self, exclude_id: int | None = None) -> Question | None:
        stmt: Select[tuple[Question]] = (
            select(Question)
            .where(Question.status.in_(["new", "pending", "manual", "failed"]))
            .order_by(Question.created_at.asc())
            .limit(1)
        )
        if exclude_id is not None:
            stmt = stmt.where(Question.id != exclude_id)
        return cast("Question | None", await self._session.scalar(stmt))

    async def count_queue(self) -> int:
        value = await self._session.scalar(
            select(func.count(Question.id)).where(
                Question.status.in_(["new", "pending", "manual", "failed"])
            )
        )
        return int(value or 0)

    async def count_answered_since(self, since: datetime) -> int:
        value = await self._session.scalar(
            select(func.count(Question.id)).where(
                Question.status == "answered",
                Question.answer_sent_at >= since,
            )
        )
        return int(value or 0)

    async def mark_missing_from_unanswered(
        self, account_id: int, active_wb_question_ids: set[str]
    ) -> list[Question]:
        result = await self._session.scalars(
            select(Question).where(
                Question.wb_account_id == account_id,
                Question.status.in_(["new", "pending", "manual", "failed"]),
            )
        )
        closed: list[Question] = []
        for question in result.all():
            if question.wb_question_id in active_wb_question_ids:
                continue
            question.status = "answered"
            closed.append(question)
        return closed

    async def restore_sending(self) -> int:
        result = await self._session.scalars(select(Question).where(Question.status == "sending"))
        count = 0
        for question in result.all():
            question.status = "pending"
            count += 1
        return count

    @staticmethod
    def today_start() -> datetime:
        return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
