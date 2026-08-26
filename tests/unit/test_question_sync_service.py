from datetime import datetime

import pytest

from app.integrations.wildberries.question_schemas import Question as WbQuestion
from app.services.question_matching_service import QuestionMatchingService
from app.services.question_rendering_service import QuestionAnswerRenderer
from app.services.question_sync_service import QuestionSyncService
from app.services.question_template_catalog import QuestionTemplateCandidate


class FakeAccount:
    id = 1
    last_successful_sync_at: datetime | None = None
    last_sync_error: str | None = None


class FakeQuestion:
    def __init__(self, status: str = "new", text: str = "Какая пленка?") -> None:
        self.id = 10
        self.wb_question_id = "q1"
        self.nm_id = 123
        self.imt_id = None
        self.product_name = "Item"
        self.supplier_article = "A-1"
        self.brand_name = "VinylStudio"
        self.question_text = text
        self.status = status
        self.selected_template_id: int | None = None
        self.answer_text: str | None = None
        self.answer_sent_at: datetime | None = None


class FakeWbClient:
    def __init__(self, text: str = "Какая пленка?", pages: int = 1) -> None:
        self.text = text
        self.pages = pages
        self.sent: list[tuple[str, str]] = []
        self.calls: list[tuple[int, int]] = []

    async def get_unanswered_questions(
        self, take: int, skip: int, order: str = "dateDesc"
    ) -> list[WbQuestion]:
        self.calls.append((take, skip))
        if skip >= take * self.pages:
            return []
        return [WbQuestion(id=f"q{skip}", text=self.text)]

    async def send_question_answer(self, question_id: str, text: str) -> None:
        self.sent.append((question_id, text))


class FakeQuestionRepo:
    def __init__(self, question: FakeQuestion) -> None:
        self.question = question
        self.closed_active_ids: set[str] | None = None

    async def upsert_from_wb(
        self, account_id: int, item: WbQuestion
    ) -> tuple[FakeQuestion, bool]:
        self.question.question_text = item.text
        return self.question, True

    async def mark_missing_from_unanswered(
        self, account_id: int, active_wb_question_ids: set[str]
    ) -> list[FakeQuestion]:
        self.closed_active_ids = active_wb_question_ids
        return []


class FakeTemplateRepo:
    def __init__(
        self,
        auto_send: bool = True,
        *,
        keywords: set[str] | None = None,
        text: str = "Пленка Spectroll",
    ) -> None:
        self.auto_send = auto_send
        self.keywords = keywords or {"пленка"}
        self.text = text

    async def list_active_candidates(self) -> list[QuestionTemplateCandidate]:
        return [
            QuestionTemplateCandidate(
                id=1,
                code="film_request",
                name="Запрос на пленку",
                category="film",
                text=self.text,
                priority=90,
                keywords=self.keywords,
                auto_send=self.auto_send,
            )
        ]


class FakeActionRepo:
    def __init__(self, already_sent: bool = False) -> None:
        self.already_sent = already_sent
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
        return action == "answer_sent" and self.already_sent


class FakeDraft:
    def __init__(self, answer_text: str | None, status: str, confidence: str) -> None:
        self.answer_text = answer_text
        self.status = status
        self.intent = "TEST"
        self.confidence = confidence
        self.reason = "test"
        self.extracted: dict[str, object] = {}
        self.matched_skus: list[str] = []


class FakeDraftService:
    def __init__(
        self,
        answer_text: str | None = "Пленка Spectroll",
        status: str = "pending",
        confidence: str = "HIGH",
    ) -> None:
        self.answer_text = answer_text
        self.status = status
        self.confidence = confidence

    def build_draft(self, context: object) -> FakeDraft:
        return FakeDraft(self.answer_text, self.status, self.confidence)


def build_service(
    question: FakeQuestion,
    wb_client: FakeWbClient,
    actions: FakeActionRepo,
    templates: FakeTemplateRepo | None = None,
    draft_service: FakeDraftService | None = None,
    auto_send_enabled: bool = False,
) -> QuestionSyncService:
    return QuestionSyncService(
        FakeAccount(),  # type: ignore[arg-type]
        wb_client,  # type: ignore[arg-type]
        FakeQuestionRepo(question),  # type: ignore[arg-type]
        templates or FakeTemplateRepo(),  # type: ignore[arg-type]
        actions,  # type: ignore[arg-type]
        QuestionMatchingService(),
        QuestionAnswerRenderer(),
        draft_service or FakeDraftService(),  # type: ignore[arg-type]
        auto_send_enabled=auto_send_enabled,
    )


@pytest.mark.asyncio
async def test_sync_prepares_safe_recognized_question_without_auto_send() -> None:
    question = FakeQuestion()
    wb_client = FakeWbClient()
    actions = FakeActionRepo()
    service = build_service(question, wb_client, actions)

    assert await service.sync(page_size=100) == (1, 1, 0)
    assert question.status == "pending"
    assert question.answer_text == "Пленка Spectroll"
    assert wb_client.sent == []
    assert "answer_sent" not in actions.actions


@pytest.mark.asyncio
async def test_sync_keeps_unknown_question_manual() -> None:
    question = FakeQuestion(text="Здравствуйте")
    wb_client = FakeWbClient(text="Здравствуйте")
    actions = FakeActionRepo()
    service = build_service(
        question, wb_client, actions, draft_service=FakeDraftService(None, "manual")
    )

    assert await service.sync(page_size=100) == (1, 1, 0)
    assert question.status == "manual"
    assert wb_client.sent == []


@pytest.mark.asyncio
async def test_sync_does_not_send_manual_confirmation_template() -> None:
    question = FakeQuestion(text="Подойдет на мой автомобиль?")
    wb_client = FakeWbClient(text="Подойдет на мой автомобиль?")
    actions = FakeActionRepo()
    service = build_service(
        question,
        wb_client,
        actions,
        FakeTemplateRepo(auto_send=False, keywords={"подойдет"}, text="Да, подойдет"),
    )

    assert await service.sync(page_size=100) == (1, 1, 0)
    assert question.status == "pending"
    assert wb_client.sent == []


@pytest.mark.asyncio
async def test_sync_does_not_send_when_sent_action_exists() -> None:
    question = FakeQuestion()
    wb_client = FakeWbClient()
    actions = FakeActionRepo(already_sent=True)
    service = build_service(question, wb_client, actions)

    assert await service.sync(page_size=100) == (1, 1, 0)
    assert question.status == "pending"
    assert wb_client.sent == []


@pytest.mark.asyncio
async def test_sync_uses_one_question_page_by_default() -> None:
    question = FakeQuestion()
    wb_client = FakeWbClient(pages=2)
    actions = FakeActionRepo()
    service = build_service(question, wb_client, actions)

    assert await service.sync(inter_page_delay_seconds=0) == (1, 1, 0)
    assert wb_client.calls == [(50, 0)]


@pytest.mark.asyncio
async def test_sync_can_load_multiple_question_pages_when_enabled() -> None:
    question = FakeQuestion()
    wb_client = FakeWbClient(pages=2)
    actions = FakeActionRepo()
    service = build_service(question, wb_client, actions)

    assert await service.sync(inter_page_delay_seconds=0, max_pages=None) == (2, 2, 0)
    assert wb_client.calls == [(50, 0), (50, 50), (50, 100)]


@pytest.mark.asyncio
async def test_sync_auto_sends_high_confidence_question_when_enabled() -> None:
    question = FakeQuestion()
    wb_client = FakeWbClient()
    actions = FakeActionRepo()
    service = build_service(question, wb_client, actions, auto_send_enabled=True)

    assert await service.sync(page_size=100) == (1, 1, 0)
    assert question.status == "answered"
    assert wb_client.sent == [("q1", "Пленка Spectroll")]
    assert "answer_sent" in actions.actions


@pytest.mark.asyncio
async def test_sync_does_not_auto_send_low_confidence_question() -> None:
    question = FakeQuestion()
    wb_client = FakeWbClient()
    actions = FakeActionRepo()
    service = build_service(
        question,
        wb_client,
        actions,
        draft_service=FakeDraftService(
            "Тема не распознана. Нужна ручная обработка.", "manual", "LOW"
        ),
        auto_send_enabled=True,
    )

    assert await service.sync(page_size=100) == (1, 1, 0)
    assert question.status == "manual"
    assert wb_client.sent == []
