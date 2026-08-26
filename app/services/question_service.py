from datetime import UTC, datetime

from app.db.models.question import Question
from app.integrations.wildberries.exceptions import WildberriesError, WildberriesRateLimitError
from app.integrations.wildberries.questions_client import WildberriesQuestionsClient
from app.repositories.question_action_repository import QuestionActionRepository
from app.repositories.question_repository import QuestionRepository


class QuestionService:
    def __init__(
        self,
        questions: QuestionRepository,
        actions: QuestionActionRepository,
        wb_client: WildberriesQuestionsClient | None = None,
    ) -> None:
        self._questions = questions
        self._actions = actions
        self._wb_client = wb_client

    async def edit_answer(self, question_id: int, text: str, telegram_user_id: int) -> Question:
        question = await self._require_question(question_id)
        old = question.status
        question.answer_text = text[:4000]
        question.edited_by_user = True
        if question.status in {"new", "manual", "failed"}:
            question.status = "pending"
        await self._actions.add(
            question.id, "answer_edited", old, question.status, telegram_user_id
        )
        return question

    async def ignore(self, question_id: int, telegram_user_id: int) -> Question:
        question = await self._require_question(question_id)
        old = question.status
        question.status = "ignored"
        await self._actions.add(question.id, "ignored", old, question.status, telegram_user_id)
        return question

    async def send_answer(self, question_id: int, telegram_user_id: int) -> Question:
        if self._wb_client is None:
            msg = "WB questions client is not configured"
            raise RuntimeError(msg)
        question = await self._require_question(question_id)
        if question.status == "answered":
            return question
        if await self._actions.has_action(question.id, "answer_sent"):
            question.status = "answered"
            return question
        if not question.answer_text:
            msg = "Question has no answer text"
            raise ValueError(msg)
        old = question.status
        question.status = "sending"
        await self._actions.add(
            question.id, "answer_send_started", old, "sending", telegram_user_id
        )
        try:
            await self._wb_client.send_question_answer(
                question.wb_question_id, question.answer_text
            )
        except WildberriesRateLimitError:
            question.status = old
            await self._actions.add(
                question.id, "send_rate_limited", "sending", old, telegram_user_id
            )
            raise
        except WildberriesError:
            question.status = "failed"
            await self._actions.add(
                question.id, "send_failed", "sending", "failed", telegram_user_id
            )
            raise
        question.status = "answered"
        question.answer_sent_at = datetime.now(UTC)
        await self._actions.add(question.id, "answer_sent", "sending", "answered", telegram_user_id)
        return question

    async def _require_question(self, question_id: int) -> Question:
        question = await self._questions.get(question_id)
        if question is None:
            msg = f"Question {question_id} not found"
            raise LookupError(msg)
        return question
