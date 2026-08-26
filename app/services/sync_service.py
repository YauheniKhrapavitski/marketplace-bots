import asyncio
import logging
from datetime import UTC, datetime

from app.db.models.account import WbAccount
from app.db.models.feedback import Feedback
from app.integrations.wildberries.client import WildberriesClient
from app.integrations.wildberries.exceptions import WildberriesRateLimitError
from app.repositories.action_repository import ActionRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.template_repository import TemplateRepository
from app.services.matching_service import FeedbackContext, MatchingService
from app.services.rendering_service import AnswerRenderer
from app.services.template_catalog import TemplateCandidate

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(
        self,
        account: WbAccount,
        wb_client: WildberriesClient,
        feedbacks: FeedbackRepository,
        templates: TemplateRepository,
        actions: ActionRepository,
        matcher: MatchingService,
        renderer: AnswerRenderer,
    ) -> None:
        self._account = account
        self._wb_client = wb_client
        self._feedbacks = feedbacks
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
            auto_publish_limited = False
            candidates = await self._templates.list_active_candidates()
            skip = 0
            while True:
                items = await self._wb_client.get_unanswered_feedbacks(take=page_size, skip=skip)
                if not items:
                    break
                received += len(items)
                for item in items:
                    feedback, was_created = await self._feedbacks.upsert_from_wb(
                        self._account.id, item
                    )
                    context = FeedbackContext(
                        wb_feedback_id=feedback.wb_feedback_id,
                        nm_id=feedback.nm_id,
                        product_name=feedback.product_name,
                        buyer_name=feedback.buyer_name,
                        rating=feedback.rating,
                        review_text=feedback.review_text,
                        pros=feedback.pros,
                        cons=feedback.cons,
                        supplier_article=feedback.supplier_article,
                    )
                    template = self._matcher.select_template(context, candidates)
                    if template is None:
                        feedback.selected_template_id = None
                        feedback.answer_text = None
                    else:
                        feedback.selected_template_id = template.id
                        feedback.answer_text = self._renderer.render(template.text, context)
                    if was_created:
                        created += 1
                        feedback.status = "pending"
                        await self._actions.add(feedback.id, "received", "new", "pending")
                        if template is not None:
                            await self._actions.add(
                                feedback.id,
                                "template_selected",
                                "pending",
                                "pending",
                                payload={"template_code": template.code},
                            )
                    else:
                        updated += 1
                    if template is not None and not auto_publish_limited:
                        try:
                            await self._send_positive_rating_answer(feedback)
                        except WildberriesRateLimitError:
                            auto_publish_limited = True
                            logger.warning(
                                "wb auto answer rate limited",
                                extra={"service": "sync", "event": "auto_answer_rate_limited"},
                            )
                skip += page_size
            if not auto_publish_limited:
                repair_received, repair_created, repair_updated = (
                    await self._repair_positive_answered_feedbacks_without_text(
                        candidates, page_size
                    )
                )
                received += repair_received
                created += repair_created
                updated += repair_updated
            self._account.last_successful_sync_at = datetime.now(UTC)
            self._account.last_sync_error = None
            logger.info("sync finished", extra={"service": "sync", "event": "sync_finished"})
            return received, created, updated

    async def _repair_positive_answered_feedbacks_without_text(
        self, candidates: list[TemplateCandidate], page_size: int
    ) -> tuple[int, int, int]:
        received = created = updated = 0
        items = await self._wb_client.get_answered_feedbacks(take=page_size, skip=0)
        for item in items:
            if item.rating not in {4, 5} or self._has_answer_text(item.raw.get("answer")):
                continue
            received += 1
            feedback, was_created = await self._feedbacks.upsert_from_wb(
                self._account.id, item
            )
            context = self._context_from_feedback(feedback)
            template = self._matcher.select_template(context, candidates)
            if template is None:
                continue
            feedback.selected_template_id = template.id
            feedback.answer_text = self._renderer.render(template.text, context)
            if was_created:
                created += 1
                feedback.status = "pending"
                await self._actions.add(
                    feedback.id,
                    "received",
                    "new",
                    "pending",
                    payload={"repair": "answered_without_text"},
                )
                await self._actions.add(
                    feedback.id,
                    "template_selected",
                    "pending",
                    "pending",
                    payload={"template_code": template.code, "repair": "answered_without_text"},
                )
            else:
                updated += 1
            await self._send_positive_rating_answer(
                feedback,
                repair_answer_without_text=True,
                answer_marker=item.raw.get("answer"),
            )
        return received, created, updated

    @staticmethod
    def _has_answer_text(answer: object) -> bool:
        return isinstance(answer, dict) and bool(str(answer.get("text") or "").strip())

    @staticmethod
    def _context_from_feedback(feedback: Feedback) -> FeedbackContext:
        return FeedbackContext(
            wb_feedback_id=feedback.wb_feedback_id,
            nm_id=feedback.nm_id,
            product_name=feedback.product_name,
            buyer_name=feedback.buyer_name,
            rating=feedback.rating,
            review_text=feedback.review_text,
            pros=feedback.pros,
            cons=feedback.cons,
            supplier_article=feedback.supplier_article,
        )

    async def _send_positive_rating_answer(
        self,
        feedback: Feedback,
        *,
        repair_answer_without_text: bool = False,
        answer_marker: object = None,
    ) -> None:
        feedback_id = feedback.id
        if feedback.status in {"ignored", "sending"}:
            return
        if feedback.status == "answered" and not repair_answer_without_text:
            return
        if (
            await self._actions.has_action(feedback_id, "answer_sent")
            and not repair_answer_without_text
        ):
            feedback.status = "answered"
            return
        if not feedback.answer_text:
            msg = "Feedback has no answer text"
            raise ValueError(msg)
        old_status = feedback.status
        feedback.status = "sending"
        await self._actions.add(
            feedback_id,
            "answer_send_started",
            old_status,
            "sending",
            payload={
                "auto": True,
                "reason": "answered_without_text_repair"
                if repair_answer_without_text
                else "positive_rating",
                "rating": feedback.rating,
            },
        )
        try:
            if repair_answer_without_text and answer_marker is True:
                await self._wb_client.edit_feedback_answer(
                    feedback.wb_feedback_id, feedback.answer_text
                )
            else:
                await self._wb_client.send_feedback_answer(
                    feedback.wb_feedback_id, feedback.answer_text
                )
        except WildberriesRateLimitError:
            feedback.status = "pending"
            await self._actions.add(
                feedback_id,
                "send_rate_limited",
                "sending",
                "pending",
                payload={
                    "auto": True,
                    "reason": "answered_without_text_repair"
                    if repair_answer_without_text
                    else "positive_rating",
                    "rating": feedback.rating,
                },
            )
            raise
        except Exception:
            feedback.status = "failed"
            await self._actions.add(
                feedback_id,
                "send_failed",
                "sending",
                "failed",
                payload={
                    "auto": True,
                    "reason": "answered_without_text_repair"
                    if repair_answer_without_text
                    else "positive_rating",
                    "rating": feedback.rating,
                },
            )
            raise
        feedback.status = "answered"
        feedback.answer_sent_at = datetime.now(UTC)
        await self._actions.add(
            feedback_id,
            "answer_sent",
            "sending",
            "answered",
            payload={
                "auto": True,
                "reason": "answered_without_text_repair"
                if repair_answer_without_text
                else "positive_rating",
                "rating": feedback.rating,
            },
        )
