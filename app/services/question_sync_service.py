import asyncio
import logging
from datetime import UTC, datetime

from app.db.models.account import WbAccount
from app.db.models.question import Question
from app.integrations.wildberries.questions_client import WildberriesQuestionsClient
from app.repositories.question_action_repository import QuestionActionRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.question_template_repository import QuestionTemplateRepository
from app.services.question_draft_service import QuestionDraftService
from app.services.question_matching_service import QuestionContext, QuestionMatchingService
from app.services.question_rendering_service import QuestionAnswerRenderer

logger = logging.getLogger(__name__)


class QuestionSyncService:
    def __init__(
        self,
        account: WbAccount,
        wb_client: WildberriesQuestionsClient,
        questions: QuestionRepository,
        templates: QuestionTemplateRepository,
        actions: QuestionActionRepository,
        matcher: QuestionMatchingService,
        renderer: QuestionAnswerRenderer,
        draft_service: QuestionDraftService | None = None,
        auto_send_enabled: bool = False,
    ) -> None:
        self._account = account
        self._wb_client = wb_client
        self._questions = questions
        self._templates = templates
        self._actions = actions
        self._matcher = matcher
        self._renderer = renderer
        self._draft_service = draft_service or QuestionDraftService()
        self._auto_send_enabled = auto_send_enabled
        self._lock = asyncio.Lock()

    async def sync(
        self,
        page_size: int = 50,
        inter_page_delay_seconds: float = 1.5,
        max_pages: int | None = 1,
    ) -> tuple[int, int, int]:
        if self._lock.locked():
            return (0, 0, 0)
        async with self._lock:
            received = created = updated = 0
            await self._templates.list_active_candidates()
            skip = 0
            pages_loaded = 0
            fetched_wb_ids: set[str] = set()
            fetched_complete_unanswered_set = False
            while True:
                if max_pages is not None and pages_loaded >= max_pages:
                    break
                items = await self._wb_client.get_unanswered_questions(take=page_size, skip=skip)
                if not items:
                    fetched_complete_unanswered_set = True
                    break
                pages_loaded += 1
                fetched_wb_ids.update(item.id for item in items)
                if len(items) < page_size:
                    fetched_complete_unanswered_set = True
                received += len(items)
                for item in items:
                    question, was_created = await self._questions.upsert_from_wb(
                        self._account.id, item
                    )
                    context = self._to_context(question)
                    draft = self._draft_service.build_draft(context)
                    if draft.answer_text is None:
                        question.selected_template_id = None
                        question.answer_text = None
                        question.status = draft.status
                    else:
                        question.selected_template_id = None
                        question.answer_text = draft.answer_text
                        if question.status in {"new", "pending", "manual"}:
                            question.status = draft.status
                    if was_created:
                        created += 1
                        await self._actions.add(
                            question.id, "received", "new", question.status
                        )
                        await self._actions.add(
                            question.id,
                            "draft_prepared",
                            question.status,
                            question.status,
                            payload={
                                "intent": draft.intent,
                                "confidence": draft.confidence,
                                "reason": draft.reason,
                                "extracted": draft.extracted,
                                "matched_skus": draft.matched_skus,
                            },
                        )
                    else:
                        updated += 1
                    if self._should_auto_send(question, draft):
                        await self._send_auto_answer(question)
                skip += page_size
                if items and inter_page_delay_seconds > 0:
                    await asyncio.sleep(inter_page_delay_seconds)
            if fetched_complete_unanswered_set:
                closed = await self._questions.mark_missing_from_unanswered(
                    self._account.id, fetched_wb_ids
                )
                for question in closed:
                    updated += 1
                    await self._actions.add(
                        question.id,
                        "closed_on_wb",
                        None,
                        "answered",
                        payload={"reason": "missing_from_unanswered_api"},
                    )
            self._account.last_successful_sync_at = datetime.now(UTC)
            self._account.last_sync_error = None
            logger.info(
                "question sync finished",
                extra={"service": "question_sync", "event": "question_sync_finished"},
            )
            return received, created, updated

    def _should_auto_send(self, question: Question, draft: object) -> bool:
        return (
            self._auto_send_enabled
            and getattr(draft, "confidence", None) == "HIGH"
            and question.status == "pending"
            and bool(question.answer_text)
        )

    async def _send_auto_answer(self, question: Question) -> None:
        if await self._actions.has_action(question.id, "answer_sent"):
            question.status = "answered"
            return
        if not question.answer_text:
            return
        old_status = question.status
        question.status = "sending"
        await self._actions.add(
            question.id,
            "answer_send_started",
            old_status,
            "sending",
            payload={"auto": True},
        )
        try:
            await self._wb_client.send_question_answer(
                question.wb_question_id, question.answer_text
            )
        except Exception:
            question.status = old_status
            await self._actions.add(
                question.id,
                "send_failed",
                "sending",
                old_status,
                payload={"auto": True},
            )
            raise
        question.status = "answered"
        question.answer_sent_at = datetime.now(UTC)
        await self._actions.add(
            question.id,
            "answer_sent",
            "sending",
            "answered",
            payload={"auto": True},
        )

    @staticmethod
    def _to_context(question: Question) -> QuestionContext:
        return QuestionContext(
            wb_question_id=question.wb_question_id,
            question_text=question.question_text,
            nm_id=question.nm_id,
            imt_id=question.imt_id,
            product_name=question.product_name,
            supplier_article=question.supplier_article,
            brand_name=question.brand_name,
        )
