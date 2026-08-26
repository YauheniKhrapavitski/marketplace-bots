from datetime import UTC, datetime

from app.db.models.ozon import OzonReview
from app.integrations.ozon.client import OzonClient
from app.integrations.ozon.exceptions import OzonError
from app.repositories.ozon_review_action_repository import OzonReviewActionRepository
from app.repositories.ozon_review_repository import OzonReviewRepository


class OzonReviewService:
    def __init__(
        self,
        reviews: OzonReviewRepository,
        actions: OzonReviewActionRepository,
        ozon_client: OzonClient | None = None,
    ) -> None:
        self._reviews = reviews
        self._actions = actions
        self._ozon_client = ozon_client

    async def edit_answer(self, review_id: int, text: str, telegram_user_id: int) -> OzonReview:
        review = await self._require_review(review_id)
        old = review.status
        review.answer_text = text[:4000]
        review.edited_by_user = True
        if review.status in {"new", "manual", "failed"}:
            review.status = "pending"
        await self._actions.add(review.id, "answer_edited", old, review.status, telegram_user_id)
        return review

    async def postpone(self, review_id: int, hours: int, telegram_user_id: int) -> OzonReview:
        review = await self._require_review(review_id)
        old = review.status
        review.status = "postponed"
        review.postponed_until = OzonReviewRepository.postpone_until(hours)
        await self._actions.add(review.id, "postponed", old, review.status, telegram_user_id)
        return review

    async def ignore(self, review_id: int, telegram_user_id: int) -> OzonReview:
        review = await self._require_review(review_id)
        old = review.status
        review.status = "ignored"
        await self._actions.add(review.id, "ignored", old, review.status, telegram_user_id)
        return review

    async def send_answer(self, review_id: int, telegram_user_id: int) -> OzonReview:
        if self._ozon_client is None:
            msg = "Ozon client is not configured"
            raise RuntimeError(msg)
        review = await self._require_review(review_id)
        if review.status == "answered":
            return review
        if review.has_official_comment or await self._actions.has_action(review.id, "answer_sent"):
            review.status = "answered"
            return review
        if not review.answer_text:
            msg = "Ozon review has no answer text"
            raise ValueError(msg)
        old = review.status
        review.status = "sending"
        await self._actions.add(review.id, "answer_send_started", old, "sending", telegram_user_id)
        try:
            await self._ozon_client.send_review_answer(review.ozon_review_id, review.answer_text)
        except OzonError:
            review.status = "failed"
            await self._actions.add(review.id, "send_failed", "sending", "failed", telegram_user_id)
            raise
        review.status = "answered"
        review.answer_sent_at = datetime.now(UTC)
        review.has_official_comment = True
        await self._actions.add(review.id, "answer_sent", "sending", "answered", telegram_user_id)
        return review

    async def _require_review(self, review_id: int) -> OzonReview:
        review = await self._reviews.get(review_id)
        if review is None:
            msg = f"Ozon review {review_id} not found"
            raise LookupError(msg)
        return review
