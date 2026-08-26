from app.integrations.ozon.schemas import OzonReview


def test_ozon_review_from_flexible_payload() -> None:
    review = OzonReview.from_ozon(
        {
            "review_id": "abc",
            "sku": 123,
            "product_name": "Film",
            "rating": 4,
            "review_text": "Good",
            "published_at": "2026-07-20T10:00:00Z",
            "is_commented": True,
        }
    )

    assert review.id == "abc"
    assert review.sku == 123
    assert review.product_name == "Film"
    assert review.rating == 4
    assert review.text == "Good"
    assert review.has_official_comment is True
