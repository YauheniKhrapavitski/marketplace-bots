import asyncio
import logging
from datetime import UTC, datetime

from app.db.models.ozon import OzonAccount, OzonReview
from app.integrations.ozon.client import OzonClient
from app.repositories.ozon_review_action_repository import OzonReviewActionRepository
from app.repositories.ozon_review_repository import OzonReviewRepository
from app.repositories.ozon_review_template_repository import OzonReviewTemplateRepository
from app.services.ozon_review_matching_service import (
    OzonReviewContext,
    OzonReviewMatchingService,
)
from app.services.ozon_review_rendering_service import OzonReviewAnswerRenderer

logger = logging.getLogger(__name__)


class OzonReviewSyncService:
    def __init__(
        self,
        account: OzonAccount,
        ozon_client: OzonClient,
        reviews: OzonReviewRepository,
        templates: OzonReviewTemplateRepository,
        actions: OzonReviewActionRepository,
        matcher: OzonReviewMatchingService,
        renderer: OzonReviewAnswerRenderer,
    ) -> None:
        self._account = account
        self._ozon_client = ozon_client
        self._reviews = reviews
        self._templates = templates
        self._actions = actions
        self._matcher = matcher
        self._renderer = renderer
        self._lock = asyncio.Lock()

    async def sync(self, page_size: int = 100) -> tuple[int, int, int]:
        if self._lock.locked():
            return (0, 0, 0)
        async with self._lock:
            received = created = updated = 0
            candidates = await self._templates.list_active_candidates()
            offset = 0
            while True:
                items = await self._ozon_client.list_reviews(limit=page_size, offset=offset)
                if not items:
                    break
                received += len(items)
                positive_reviews: list[OzonReview] = []
                for item in items:
                    review, was_created = await self._reviews.upsert_from_ozon(
                        self._account.id, item
                    )
                    context = self._to_context(review)
                    template = self._matcher.select_template(context, candidates)
                    if template is None:
                        review.selected_template_id = None
                        review.answer_text = None
                        if review.status in {"new", "pending"}:
                            review.status = "manual"
                    else:
                        review.selected_template_id = template.id
                        review.answer_text = self._renderer.render(template.text, context)
                        if review.status == "new":
                            review.status = "pending"
                    if was_created:
                        created += 1
                        await self._actions.add(review.id, "received", "new", review.status)
                        if template is not None:
                            await self._actions.add(
                                review.id,
                                "template_selected",
                                review.status,
                                review.status,
                                payload={
                                    "template_code": template.code,
                                    "auto_send": template.auto_send,
                                },
                            )
                    else:
                        updated += 1
                    if review.rating in {4, 5} and await self._prepare_positive_review(review):
                        positive_reviews.append(review)
                await self._mark_positive_reviews_processed(positive_reviews)
                offset += page_size
            self._account.last_successful_sync_at = datetime.now(UTC)
            self._account.last_sync_error = None
            logger.info(
                "ozon review sync finished",
                extra={"service": "ozon_review_sync", "event": "ozon_review_sync_finished"},
            )
            return received, created, updated

    async def _prepare_positive_review(self, review: OzonReview) -> bool:
        review_id = review.id
        if review.status in {"processed", "sending"}:
            return False
        if review.ozon_status == "PROCESSED" or await self._actions.has_action(
            review_id, "marked_processed"
        ):
            review.status = "processed"
            return False
        old_status = review.status
        review.status = "sending"
        await self._actions.add(
            review_id,
            "mark_processed_started",
            old_status,
            "sending",
            payload={"auto": True, "reason": "positive_rating_read", "rating": review.rating},
        )
        return True

    async def _mark_positive_reviews_processed(self, reviews: list[OzonReview]) -> None:
        if not reviews:
            return
        try:
            await self._ozon_client.mark_reviews_processed(
                [review.ozon_review_id for review in reviews]
            )
        except Exception as exc:
            detail = getattr(exc, "detail", "")
            for review in reviews:
                review.status = "failed"
                await self._actions.add(
                    review.id,
                    "mark_processed_failed",
                    "sending",
                    "failed",
                    payload={
                        "auto": True,
                        "reason": "positive_rating_read",
                        "rating": review.rating,
                        "error": type(exc).__name__,
                        "detail": detail,
                    },
                )
            raise
        for review in reviews:
            review.status = "processed"
            review.ozon_status = "PROCESSED"
            await self._actions.add(
                review.id,
                "marked_processed",
                "sending",
                "processed",
                payload={
                    "auto": True,
                    "reason": "positive_rating_read",
                    "rating": review.rating,
                },
            )

    @staticmethod
    def _to_context(review: OzonReview) -> OzonReviewContext:
        return OzonReviewContext(
            ozon_review_id=review.ozon_review_id,
            rating=review.rating,
            sku=review.sku,
            product_id=review.product_id,
            offer_id=review.offer_id,
            product_name=review.product_name,
            buyer_name=review.buyer_name,
            review_text=review.review_text,
            pros=review.pros,
            cons=review.cons,
            has_official_comment=review.has_official_comment,
        )
