from app.services.ozon_review_matching_service import (
    OzonReviewContext,
    OzonReviewMatchingService,
)
from app.services.ozon_review_template_catalog import OzonReviewTemplateCandidate


def test_selects_positive_template_by_rating() -> None:
    template = OzonReviewTemplateCandidate(
        id=1,
        code="ozon_rating_5_positive",
        name="Positive",
        category="positive",
        text="Thanks",
        priority=1,
        ratings={5},
    )
    review = OzonReviewContext(ozon_review_id="r1", rating=5, review_text="Great")

    assert OzonReviewMatchingService().select_template(review, [template]) == template


def test_known_negative_topic_selects_keyword_template_even_with_risky_words() -> None:
    template = OzonReviewTemplateCandidate(
        id=1,
        code="ozon_film_quality_negative",
        name="Quality",
        category="negative_quality",
        text="Please contact us",
        priority=1,
        ratings={1, 2, 3},
        keywords={"quality"},
    )
    review = OzonReviewContext(
        ozon_review_id="r1",
        rating=1,
        review_text="Bad quality, I want a refund",
    )

    assert OzonReviewMatchingService().select_template(review, [template]) == template


def test_unknown_negative_topic_stays_manual() -> None:
    template = OzonReviewTemplateCandidate(
        id=1,
        code="ozon_packaging_damage",
        name="Packaging",
        category="packaging",
        text="Pack",
        priority=1,
        ratings={1, 2, 3},
        keywords={"box"},
    )
    review = OzonReviewContext(ozon_review_id="r1", rating=1, review_text="I did not like it")

    assert OzonReviewMatchingService().select_template(review, [template]) is None


def test_negative_without_text_selects_no_text_template() -> None:
    template = OzonReviewTemplateCandidate(
        id=1,
        code="ozon_negative_no_text",
        name="No text",
        category="negative_no_text",
        text="Please describe",
        priority=1,
        ratings={1, 2, 3},
    )
    review = OzonReviewContext(ozon_review_id="r1", rating=2, review_text=None)

    assert OzonReviewMatchingService().select_template(review, [template]) == template
