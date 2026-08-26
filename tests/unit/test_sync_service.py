from datetime import datetime

import pytest

from app.integrations.wildberries.exceptions import WildberriesRateLimitError
from app.integrations.wildberries.schemas import Feedback as WbFeedback
from app.services.matching_service import MatchingService
from app.services.rendering_service import AnswerRenderer
from app.services.sync_service import SyncService
from app.services.template_catalog import TemplateCandidate


class FakeAccount:
    id = 1
    last_successful_sync_at: datetime | None = None
    last_sync_error: str | None = None


class FakeFeedback:
    def __init__(
        self, rating: int = 5, status: str = "new", review_text: str | None = "Great"
    ) -> None:
        self.id = 10
        self.wb_feedback_id = "fb1"
        self.nm_id = 123
        self.product_name = "Item"
        self.supplier_article = "A-1"
        self.buyer_name = None
        self.rating = rating
        self.review_text = review_text
        self.pros = None
        self.cons = None
        self.status = status
        self.selected_template_id: int | None = None
        self.answer_text: str | None = None
        self.answer_sent_at: datetime | None = None


class FakeWbClient:
    def __init__(
        self,
        rating: int = 5,
        text: str | None = "Great",
        answered_items: list[WbFeedback] | None = None,
        rate_limit_on_send: bool = False,
    ) -> None:
        self.rating = rating
        self.text = text
        self.answered_items = answered_items or []
        self.rate_limit_on_send = rate_limit_on_send
        self.sent: list[tuple[str, str]] = []
        self.edited: list[tuple[str, str]] = []

    async def get_unanswered_feedbacks(
        self, take: int, skip: int, order: str = "dateDesc"
    ) -> list[WbFeedback]:
        if skip:
            return []
        return [WbFeedback(id="fb1", rating=self.rating, text=self.text)]

    async def get_answered_feedbacks(
        self, take: int, skip: int, order: str = "dateDesc"
    ) -> list[WbFeedback]:
        if skip:
            return []
        return self.answered_items

    async def send_feedback_answer(self, feedback_id: str, text: str) -> None:
        if self.rate_limit_on_send:
            raise WildberriesRateLimitError("limited")
        self.sent.append((feedback_id, text))

    async def edit_feedback_answer(self, feedback_id: str, text: str) -> None:
        self.edited.append((feedback_id, text))


class FakeFeedbackRepo:
    def __init__(self, feedback: FakeFeedback) -> None:
        self.feedback = feedback
        self.seen_ids: set[str] = set()

    async def upsert_from_wb(
        self, account_id: int, item: WbFeedback
    ) -> tuple[FakeFeedback, bool]:
        was_created = item.id not in self.seen_ids
        self.seen_ids.add(item.id)
        self.feedback.wb_feedback_id = item.id
        self.feedback.rating = item.rating
        self.feedback.review_text = item.text
        return self.feedback, was_created


class FakeTemplateRepo:
    async def list_active_candidates(self) -> list[TemplateCandidate]:
        return [
            TemplateCandidate(
                id=1,
                code="five",
                name="Five",
                category="positive",
                text="{{buyer_greeting}} Thanks for five",
                priority=1,
                ratings={5},
            ),
            TemplateCandidate(
                id=2,
                code="four",
                name="Four",
                category="positive",
                text="{{buyer_greeting}} Thanks for four",
                priority=1,
                ratings={4},
            ),
            TemplateCandidate(
                id=3,
                code="negative_fallback",
                name="Negative fallback",
                category="negative_no_text",
                text="{{buyer_greeting}} Tell us more",
                priority=1,
                ratings={1, 2, 3},
            ),
            TemplateCandidate(
                id=4,
                code="default",
                name="Default",
                category="default",
                text="{{buyer_greeting}} Thanks",
                priority=0,
                is_default=True,
            ),
        ]


class FakeActionRepo:
    def __init__(self, already_sent: bool = False) -> None:
        self.already_sent = already_sent
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
        return action == "answer_sent" and self.already_sent


def build_service(
    feedback: FakeFeedback, wb_client: FakeWbClient, actions: FakeActionRepo
) -> SyncService:
    return SyncService(
        FakeAccount(),  # type: ignore[arg-type]
        wb_client,  # type: ignore[arg-type]
        FakeFeedbackRepo(feedback),  # type: ignore[arg-type]
        FakeTemplateRepo(),  # type: ignore[arg-type]
        actions,  # type: ignore[arg-type]
        MatchingService(),
        AnswerRenderer(),
    )


@pytest.mark.asyncio
async def test_sync_auto_sends_five_star_feedback() -> None:
    feedback = FakeFeedback(rating=5)
    wb_client = FakeWbClient(rating=5)
    actions = FakeActionRepo()
    service = build_service(feedback, wb_client, actions)

    assert await service.sync(page_size=100) == (1, 1, 0)
    assert feedback.status == "answered"
    assert wb_client.sent == [("fb1", "Здравствуйте! Thanks for five")]
    assert "answer_sent" in actions.actions


@pytest.mark.asyncio
async def test_sync_auto_sends_four_star_feedback_without_text() -> None:
    feedback = FakeFeedback(rating=4, review_text=None)
    wb_client = FakeWbClient(rating=4, text=None)
    actions = FakeActionRepo()
    service = build_service(feedback, wb_client, actions)

    assert await service.sync(page_size=100) == (1, 1, 0)
    assert feedback.status == "answered"
    assert wb_client.sent == [("fb1", "Здравствуйте! Thanks for four")]
    assert "answer_sent" in actions.actions


@pytest.mark.asyncio
async def test_sync_keeps_positive_feedback_pending_when_auto_send_is_rate_limited() -> None:
    feedback = FakeFeedback(rating=5)
    wb_client = FakeWbClient(rating=5, rate_limit_on_send=True)
    actions = FakeActionRepo()
    service = build_service(feedback, wb_client, actions)

    assert await service.sync(page_size=100) == (1, 1, 0)
    assert feedback.status == "pending"
    assert feedback.answer_text is not None
    assert feedback.answer_text.endswith("Thanks for five")
    assert wb_client.sent == []
    assert "send_rate_limited" in actions.actions
    assert "answer_sent" not in actions.actions


@pytest.mark.asyncio
async def test_sync_repairs_answered_positive_feedback_without_answer_text() -> None:
    answered_without_text = WbFeedback(
        id="answered1",
        rating=5,
        text=None,
        raw={"id": "answered1", "productValuation": 5, "text": "", "answer": True},
    )
    feedback = FakeFeedback(rating=5)
    wb_client = FakeWbClient(rating=3, answered_items=[answered_without_text])
    actions = FakeActionRepo()
    service = build_service(feedback, wb_client, actions)

    assert await service.sync(page_size=100) == (2, 2, 0)
    assert wb_client.edited == [("answered1", "Здравствуйте! Thanks for five")]
    assert feedback.status == "answered"
    assert "answer_sent" in actions.actions


@pytest.mark.asyncio
async def test_sync_does_not_repair_answered_feedback_with_answer_text() -> None:
    answered_with_text = WbFeedback(
        id="answered1",
        rating=5,
        text=None,
        raw={
            "id": "answered1",
            "productValuation": 5,
            "text": "",
            "answer": {"text": "Already answered"},
        },
    )
    feedback = FakeFeedback(rating=3)
    wb_client = FakeWbClient(rating=3, answered_items=[answered_with_text])
    actions = FakeActionRepo()
    service = build_service(feedback, wb_client, actions)

    assert await service.sync(page_size=100) == (1, 1, 0)
    assert wb_client.edited == []


@pytest.mark.asyncio
async def test_sync_auto_sends_lower_rating_feedback_with_fallback_template() -> None:
    feedback = FakeFeedback(rating=3)
    wb_client = FakeWbClient(rating=3)
    actions = FakeActionRepo()
    service = build_service(feedback, wb_client, actions)

    assert await service.sync(page_size=100) == (1, 1, 0)
    assert feedback.status == "answered"
    assert wb_client.sent
    assert wb_client.sent[0][0] == "fb1"
    assert wb_client.sent[0][1].endswith("Tell us more")
    assert "answer_sent" in actions.actions
