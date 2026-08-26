from datetime import UTC, datetime

from app.db.models.feedback import Feedback
from app.integrations.wildberries.client import WildberriesClient
from app.integrations.wildberries.exceptions import WildberriesError
from app.repositories.action_repository import ActionRepository
from app.repositories.feedback_repository import FeedbackRepository


class FeedbackService:
    def __init__(
        self,
        feedbacks: FeedbackRepository,
        actions: ActionRepository,
        wb_client: WildberriesClient | None = None,
    ) -> None:
        self._feedbacks = feedbacks
        self._actions = actions
        self._wb_client = wb_client

    async def edit_answer(self, feedback_id: int, text: str, telegram_user_id: int) -> Feedback:
        feedback = await self._require_feedback(feedback_id)
        old = feedback.status
        feedback.answer_text = text[:4000]
        feedback.edited_by_user = True
        if feedback.status == "new":
            feedback.status = "pending"
        await self._actions.add(
            feedback.id, "answer_edited", old, feedback.status, telegram_user_id
        )
        return feedback

    async def postpone(self, feedback_id: int, hours: int, telegram_user_id: int) -> Feedback:
        feedback = await self._require_feedback(feedback_id)
        old = feedback.status
        feedback.status = "postponed"
        feedback.postponed_until = FeedbackRepository.postpone_until(hours)
        await self._actions.add(feedback.id, "postponed", old, feedback.status, telegram_user_id)
        return feedback

    async def ignore(self, feedback_id: int, telegram_user_id: int) -> Feedback:
        feedback = await self._require_feedback(feedback_id)
        old = feedback.status
        feedback.status = "ignored"
        await self._actions.add(feedback.id, "ignored", old, feedback.status, telegram_user_id)
        return feedback

    async def send_answer(self, feedback_id: int, telegram_user_id: int) -> Feedback:
        if self._wb_client is None:
            msg = "WB client is not configured"
            raise RuntimeError(msg)
        feedback = await self._require_feedback(feedback_id)
        if feedback.status == "answered":
            return feedback
        if await self._actions.has_action(feedback.id, "answer_sent"):
            feedback.status = "answered"
            return feedback
        if not feedback.answer_text:
            msg = "Feedback has no answer text"
            raise ValueError(msg)
        old = feedback.status
        feedback.status = "sending"
        await self._actions.add(
            feedback.id, "answer_send_started", old, "sending", telegram_user_id
        )
        try:
            await self._wb_client.send_feedback_answer(
                feedback.wb_feedback_id, feedback.answer_text
            )
        except WildberriesError:
            feedback.status = "failed"
            await self._actions.add(
                feedback.id, "send_failed", "sending", "failed", telegram_user_id
            )
            raise
        feedback.status = "answered"
        feedback.answer_sent_at = datetime.now(UTC)
        await self._actions.add(feedback.id, "answer_sent", "sending", "answered", telegram_user_id)
        return feedback

    async def _require_feedback(self, feedback_id: int) -> Feedback:
        feedback = await self._feedbacks.get(feedback_id)
        if feedback is None:
            msg = f"Feedback {feedback_id} not found"
            raise LookupError(msg)
        return feedback
