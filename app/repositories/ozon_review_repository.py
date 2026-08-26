from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ozon import OzonReview
from app.integrations.ozon.schemas import OzonReview as OzonApiReview


class OzonReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_from_ozon(
        self, account_id: int, item: OzonApiReview
    ) -> tuple[OzonReview, bool]:
        existing = await self.get_by_ozon_id(account_id, item.id)
        if existing:
            existing.rating = item.rating
            existing.review_text = item.text
            existing.pros = item.pros
            existing.cons = item.cons
            existing.ozon_status = item.status
            existing.has_official_comment = item.has_official_comment
            existing.raw_payload = item.raw
            return existing, False
        review = OzonReview(
            ozon_account_id=account_id,
            ozon_review_id=item.id,
            sku=item.sku,
            product_id=item.product_id,
            offer_id=item.offer_id,
            product_name=item.product_name,
            buyer_name=item.buyer_name,
            rating=item.rating,
            review_text=item.text,
            pros=item.pros,
            cons=item.cons,
            published_at_ozon=item.published_at,
            ozon_status=item.status,
            has_official_comment=item.has_official_comment,
            raw_payload=item.raw,
            status="new",
        )
        self._session.add(review)
        await self._session.flush()
        return review, True

    async def get_by_ozon_id(self, account_id: int, ozon_review_id: str) -> OzonReview | None:
        result = await self._session.scalar(
            select(OzonReview).where(
                OzonReview.ozon_account_id == account_id,
                OzonReview.ozon_review_id == ozon_review_id,
            )
        )
        return cast("OzonReview | None", result)

    async def get(self, review_id: int) -> OzonReview | None:
        return await self._session.get(OzonReview, review_id)

    async def next_pending(self) -> OzonReview | None:
        now = datetime.now(UTC)
        stmt: Select[tuple[OzonReview]] = (
            select(OzonReview)
            .where(
                OzonReview.status.in_(["new", "pending", "manual", "failed", "postponed"]),
                (OzonReview.postponed_until.is_(None)) | (OzonReview.postponed_until <= now),
            )
            .order_by(OzonReview.created_at.asc())
            .limit(1)
        )
        return cast("OzonReview | None", await self._session.scalar(stmt))

    async def count_queue(self) -> int:
        now = datetime.now(UTC)
        value = await self._session.scalar(
            select(func.count(OzonReview.id)).where(
                OzonReview.status.in_(["new", "pending", "manual", "failed", "postponed"]),
                (OzonReview.postponed_until.is_(None)) | (OzonReview.postponed_until <= now),
            )
        )
        return int(value or 0)

    async def count_answered_since(self, since: datetime) -> int:
        value = await self._session.scalar(
            select(func.count(OzonReview.id)).where(
                OzonReview.status == "answered",
                OzonReview.answer_sent_at >= since,
            )
        )
        return int(value or 0)

    async def restore_sending(self) -> int:
        result = await self._session.scalars(
            select(OzonReview).where(OzonReview.status == "sending")
        )
        count = 0
        for review in result.all():
            review.status = "pending"
            count += 1
        return count

    @staticmethod
    def postpone_until(hours: int) -> datetime:
        return datetime.now(UTC) + timedelta(hours=hours)
