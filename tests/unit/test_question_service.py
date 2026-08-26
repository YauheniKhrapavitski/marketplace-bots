from dataclasses import dataclass
from datetime import datetime

import pytest

from app.integrations.wildberries.exceptions import WildberriesRateLimitError
from app.services.question_service import QuestionService


@dataclass
class FakeQuestion:
    id: int = 1
    wb_question_id: str = "q1"
    status: str = "manual"
    answer_text: str | None = None
    answer_sent_at: datetime | None = None
    edited_by_user: bool = False


class FakeQuestionRepo:
    def __init__(self, question: FakeQuestion) -> None:
        self.question = question

    async def get(self, question_id: int) -> FakeQuestion | None:
        return self.question if question_id == self.question.id else None


class FakeActionRepo:
    def __init__(self, sent: bool = False) -> None:
        self.sent = sent
        self.actions: list[str] = []

    async def add(
        self,
        question_id: int,
        action: str,
        old_status: str | None,
        new_status: str | None,
        telegram_user_id: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        self.actions.append(action)

    async def has_action(self, question_id: int, action: str) -> bool:
        return action == "answer_sent" and self.sent


class FakeWbClient:
    def __init__(self, rate_limited: bool = False) -> None:
        self.calls = 0
        self.rate_limited = rate_limited
        self.sent: list[tuple[str, str]] = []

    async def send_question_answer(self, question_id: str, text: str) -> None:
        self.calls += 1
        if self.rate_limited:
            raise WildberriesRateLimitError("limited")
        self.sent.append((question_id, text))


@pytest.mark.asyncio
async def test_edit_answer_prepares_manual_question_for_sending() -> None:
    question = FakeQuestion(status="manual")
    actions = FakeActionRepo()
    service = QuestionService(FakeQuestionRepo(question), actions)  # type: ignore[arg-type]

    result = await service.edit_answer(1, "Добрый день, подойдет.", 42)

    assert result.status == "pending"
    assert result.answer_text == "Добрый день, подойдет."
    assert result.edited_by_user is True
    assert "answer_edited" in actions.actions


@pytest.mark.asyncio
async def test_send_answer_calls_wb_once() -> None:
    question = FakeQuestion(status="pending", answer_text="Ответ")
    actions = FakeActionRepo()
    client = FakeWbClient()
    service = QuestionService(FakeQuestionRepo(question), actions, client)  # type: ignore[arg-type]

    result = await service.send_answer(1, 42)

    assert result.status == "answered"
    assert client.sent == [("q1", "Ответ")]
    assert "answer_sent" in actions.actions


@pytest.mark.asyncio
async def test_send_answer_keeps_pending_status_on_rate_limit() -> None:
    question = FakeQuestion(status="pending", answer_text="Ответ")
    actions = FakeActionRepo()
    client = FakeWbClient(rate_limited=True)
    service = QuestionService(FakeQuestionRepo(question), actions, client)  # type: ignore[arg-type]

    with pytest.raises(WildberriesRateLimitError):
        await service.send_answer(1, 42)

    assert question.status == "pending"
    assert "send_rate_limited" in actions.actions
