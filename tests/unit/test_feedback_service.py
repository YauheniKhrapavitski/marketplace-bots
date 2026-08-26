from dataclasses import dataclass
from datetime import datetime

import pytest

from app.services.feedback_service import FeedbackService


@dataclass
class FakeFeedback:
    id: int = 1
    wb_feedback_id: str = "fb1"
    status: str = "pending"
    answer_text: str | None = "Спасибо"
    answer_sent_at: datetime | None = None
    edited_by_user: bool = False


class FakeFeedbackRepo:
    def __init__(self, feedback: FakeFeedback) -> None:
        self.feedback = feedback

    async def get(self, feedback_id: int) -> FakeFeedback | None:
        return self.feedback if feedback_id == self.feedback.id else None


class FakeActionRepo:
    def __init__(self, sent: bool = False) -> None:
        self.sent = sent
        self.actions: list[str] = []

    async def add(
        self,
        feedback_id: int,
        action: str,
        old_status: str | None,
        new_status: str | None,
        telegram_user_id: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        self.actions.append(action)

    async def has_action(self, feedback_id: int, action: str) -> bool:
        return action == "answer_sent" and self.sent


class FakeWbClient:
    def __init__(self) -> None:
        self.calls = 0

    async def send_feedback_answer(self, feedback_id: str, text: str) -> None:
        self.calls += 1


@pytest.mark.asyncio
async def test_edit_answer_saves_manual_feedback_answer() -> None:
    feedback = FakeFeedback(status="pending", answer_text="Старый ответ")
    actions = FakeActionRepo()
    service = FeedbackService(FakeFeedbackRepo(feedback), actions)  # type: ignore[arg-type]

    result = await service.edit_answer(1, "Новый ответ", 42)

    assert result.answer_text == "Новый ответ"
    assert result.edited_by_user is True
    assert result.status == "pending"
    assert "answer_edited" in actions.actions


@pytest.mark.asyncio
async def test_send_answer_is_idempotent_when_already_answered_action_exists() -> None:
    feedback = FakeFeedback(status="pending")
    actions = FakeActionRepo(sent=True)
    client = FakeWbClient()
    service = FeedbackService(FakeFeedbackRepo(feedback), actions, client)  # type: ignore[arg-type]
    result = await service.send_answer(1, 42)
    assert result.status == "answered"
    assert client.calls == 0


@pytest.mark.asyncio
async def test_send_answer_calls_wb_once() -> None:
    feedback = FakeFeedback(status="pending")
    actions = FakeActionRepo()
    client = FakeWbClient()
    service = FeedbackService(FakeFeedbackRepo(feedback), actions, client)  # type: ignore[arg-type]
    result = await service.send_answer(1, 42)
    assert result.status == "answered"
    assert client.calls == 1
    assert "answer_sent" in actions.actions
