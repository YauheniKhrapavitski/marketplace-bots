from datetime import datetime

import pytest

from app.integrations.ozon.schemas import OzonReview as OzonApiReview
from app.services.ozon_review_matching_service import OzonReviewMatchingService
from app.services.ozon_review_rendering_service import OzonReviewAnswerRenderer
from app.services.ozon_review_sync_service import OzonReviewSyncService
from app.services.ozon_review_template_catalog import OzonReviewTemplateCandidate


class FakeOzonAccount:
    id = 1
    last_successful_sync_at: datetime | None = None
    last_sync_error: str | None = None


class FakeOzonReview:
    def __init__(self, rating: int = 5, text: str | None = None) -> None:
        self.id = 10
        self.ozon_review_id = "ozon-review-1"
        self.sku = 123
        self.product_id = None
        self.offer_id = None
        self.product_name = None
        self.buyer_name = None
        self.rating = rating
        self.review_text = text
        self.pros = None
        self.cons = None
        self.status = "new"
        self.selected_template_id: int | None = None
        self.answer_text: str | None = None
        self.answer_sent_at: datetime | None = None
        self.has_official_comment = False
        self.ozon_status: str | None = "UNPROCESSED"


class FakeOzonClient:
    def __init__(self, rating: int = 5, text: str | None = None) -> None:
        self.rating = rating
        self.text = text
        self.sent: list[tuple[str, str]] = []
        self.processed: list[list[str]] = []

    async def list_reviews(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        sort_dir: str = "DESC",
    ) -> list[OzonApiReview]:
        if offset:
            return []
        return [OzonApiReview(id="ozon-review-1", rating=self.rating, text=self.text)]

    async def send_review_answer(self, review_id: str, text: str) -> None:
        self.sent.append((review_id, text))

    async def mark_reviews_processed(self, review_ids: list[str]) -> None:
        self.processed.append(review_ids)


class FakeOzonReviewRepo:
    def __init__(self, review: FakeOzonReview) -> None:
        self.review = review
        self.seen_ids: set[str] = set()

    async def upsert_from_ozon(
        self, account_id: int, item: OzonApiReview
    ) -> tuple[FakeOzonReview, bool]:
        was_created = item.id not in self.seen_ids
        self.seen_ids.add(item.id)
        self.review.ozon_review_id = item.id
        self.review.rating = item.rating
        self.review.review_text = item.text
        return self.review, was_created


class FakeMultipleOzonReviewRepo:
    def __init__(self) -> None:
        self.reviews: dict[str, FakeOzonReview] = {}

    async def upsert_from_ozon(
        self, account_id: int, item: OzonApiReview
    ) -> tuple[FakeOzonReview, bool]:
        review = FakeOzonReview(rating=item.rating, text=item.text)
        review.id = len(self.reviews) + 1
        review.ozon_review_id = item.id
        self.reviews[item.id] = review
        return review, True


class FakeOzonTemplateRepo:
    async def list_active_candidates(self) -> list[OzonReviewTemplateCandidate]:
        return [
            OzonReviewTemplateCandidate(
                id=1,
                code="ozon_rating_5_positive",
                name="Five",
                category="positive",
                text="{{buyer_greeting}} Спасибо за оценку.",
                priority=1,
                ratings={5},
                auto_send=True,
            ),
            OzonReviewTemplateCandidate(
                id=2,
                code="ozon_rating_4_positive",
                name="Four",
                category="positive",
                text="{{buyer_greeting}} Спасибо за отзыв.",
                priority=1,
                ratings={4},
                auto_send=True,
            ),
        ]


class FakeOzonActionRepo:
    def __init__(self, already_processed: bool = False) -> None:
        self.already_processed = already_processed
        self.actions: list[str] = []

    async def add(
        self,
        review_id: int,
        action: str,
        old_status: str | None,
        new_status: str | None,
        telegram_user_id: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        self.actions.append(action)

    async def has_action(self, review_id: int, action: str) -> bool:
        return action == "marked_processed" and self.already_processed


def build_service(
    review: FakeOzonReview, client: FakeOzonClient, actions: FakeOzonActionRepo
) -> OzonReviewSyncService:
    return OzonReviewSyncService(
        FakeOzonAccount(),  # type: ignore[arg-type]
        client,  # type: ignore[arg-type]
        FakeOzonReviewRepo(review),  # type: ignore[arg-type]
        FakeOzonTemplateRepo(),  # type: ignore[arg-type]
        actions,  # type: ignore[arg-type]
        OzonReviewMatchingService(),
        OzonReviewAnswerRenderer(),
    )


@pytest.mark.asyncio
async def test_ozon_sync_marks_empty_five_star_processed_without_comment() -> None:
    review = FakeOzonReview(rating=5, text=None)
    client = FakeOzonClient(rating=5, text=None)
    actions = FakeOzonActionRepo()

    assert await build_service(review, client, actions).sync() == (1, 1, 0)
    assert review.status == "processed"
    assert review.ozon_status == "PROCESSED"
    assert client.sent == []
    assert client.processed == [["ozon-review-1"]]
    assert "marked_processed" in actions.actions


@pytest.mark.asyncio
async def test_ozon_sync_marks_five_star_with_text_processed_without_comment() -> None:
    review = FakeOzonReview(rating=5, text="Все отлично")
    client = FakeOzonClient(rating=5, text="Все отлично")
    actions = FakeOzonActionRepo()

    assert await build_service(review, client, actions).sync() == (1, 1, 0)
    assert review.status == "processed"
    assert review.ozon_status == "PROCESSED"
    assert client.sent == []
    assert client.processed == [["ozon-review-1"]]
    assert "marked_processed" in actions.actions


@pytest.mark.asyncio
async def test_ozon_sync_does_not_auto_send_three_star() -> None:
    review = FakeOzonReview(rating=3, text="Не подошло")
    client = FakeOzonClient(rating=3, text="Не подошло")
    actions = FakeOzonActionRepo()

    assert await build_service(review, client, actions).sync() == (1, 1, 0)
    assert review.status == "manual"
    assert client.sent == []
    assert client.processed == []


@pytest.mark.asyncio
async def test_ozon_sync_marks_positive_reviews_in_one_batch() -> None:
    client = FakeOzonClient()

    async def list_reviews(
        *, limit: int, offset: int, status: str | None = None, sort_dir: str = "DESC"
    ) -> list[OzonApiReview]:
        if offset:
            return []
        return [
            OzonApiReview(id="review-1", rating=5, text="Отлично"),
            OzonApiReview(id="review-2", rating=4, text="Хорошо"),
        ]

    client.list_reviews = list_reviews  # type: ignore[method-assign]
    actions = FakeOzonActionRepo()
    service = OzonReviewSyncService(
        FakeOzonAccount(),  # type: ignore[arg-type]
        client,  # type: ignore[arg-type]
        FakeMultipleOzonReviewRepo(),  # type: ignore[arg-type]
        FakeOzonTemplateRepo(),  # type: ignore[arg-type]
        actions,  # type: ignore[arg-type]
        OzonReviewMatchingService(),
        OzonReviewAnswerRenderer(),
    )

    assert await service.sync() == (2, 2, 0)
    assert client.processed == [["review-1", "review-2"]]
