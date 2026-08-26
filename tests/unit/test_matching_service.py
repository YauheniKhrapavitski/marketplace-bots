from app.services.matching_service import FeedbackContext, MatchingService, normalize_feedback_text
from app.services.rendering_service import AnswerRenderer
from app.services.template_catalog import TemplateCandidate


def test_selects_positive_rating_template() -> None:
    templates = [
        TemplateCandidate(1, "positive", "Positive", "positive", "ok", 1, ratings={5}),
        TemplateCandidate(2, "default", "Default", "default", "fallback", 0, is_default=True),
    ]
    selected = MatchingService().select_template(
        FeedbackContext(wb_feedback_id="f1", rating=5, review_text=None),
        templates,
    )
    assert selected is not None
    assert selected.code == "positive"


def test_keyword_overrides_positive_rating() -> None:
    templates = [
        TemplateCandidate(1, "positive", "Positive", "positive", "ok", 1, ratings={5}),
        TemplateCandidate(
            2, "packaging", "Packaging", "packaging", "pack", 100, keywords={"коробка"}
        ),
        TemplateCandidate(3, "default", "Default", "default", "fallback", 0, is_default=True),
    ]
    selected = MatchingService().select_template(
        FeedbackContext(
            wb_feedback_id="f1",
            rating=5,
            review_text="Товар хороший, но коробка помята",
        ),
        templates,
    )
    assert selected is not None
    assert selected.code == "packaging"


def test_product_keyword_has_highest_priority() -> None:
    templates = [
        TemplateCandidate(
            1, "global_pack", "Global", "packaging", "global", 100, keywords={"коробка"}
        ),
        TemplateCandidate(
            2,
            "product_pack",
            "Product",
            "packaging",
            "product",
            1,
            keywords={"коробка"},
            products={123},
        ),
    ]
    selected = MatchingService().select_template(
        FeedbackContext(wb_feedback_id="f1", rating=5, nm_id=123, review_text="Коробка вскрыта"),
        templates,
    )
    assert selected is not None
    assert selected.code == "product_pack"


def test_negative_rating_with_known_topic_selects_keyword_template() -> None:
    selected = MatchingService().select_template(
        FeedbackContext(wb_feedback_id="f1", rating=2, review_text="Коробка пришла помятая"),
        [
            TemplateCandidate(
                1,
                "packaging",
                "Packaging",
                "packaging",
                "pack",
                100,
                ratings={1, 2, 3},
                keywords={"коробка"},
            ),
            TemplateCandidate(2, "default", "Default", "default", "fallback", 0, is_default=True),
        ],
    )
    assert selected is not None
    assert selected.code == "packaging"


def test_negative_rating_uses_universal_negative_template_when_available() -> None:
    selected = MatchingService().select_template(
        FeedbackContext(wb_feedback_id="f1", rating=2, review_text="РљРѕСЂРѕР±РєР° РїРѕРјСЏС‚Р°"),
        [
            TemplateCandidate(
                1,
                "packaging",
                "Packaging",
                "packaging",
                "pack",
                100,
                ratings={1, 2, 3},
                keywords={"РєРѕСЂРѕР±РєР°"},
            ),
            TemplateCandidate(
                2,
                "negative_no_text",
                "Universal negative",
                "negative_no_text",
                "universal",
                200,
                ratings={1, 2, 3},
            ),
        ],
    )
    assert selected is not None
    assert selected.code == "negative_no_text"


def test_negative_rating_with_crumpled_film_selects_quality_template() -> None:
    selected = MatchingService().select_template(
        FeedbackContext(wb_feedback_id="f1", rating=3, cons="Мятая плёнка"),
        [
            TemplateCandidate(
                1,
                "film_quality_negative",
                "Film quality",
                "negative_quality",
                "quality",
                120,
                ratings={1, 2, 3},
                keywords={"мятая пленка"},
            ),
            TemplateCandidate(
                2,
                "packaging",
                "Packaging",
                "packaging",
                "pack",
                100,
                ratings={1, 2, 3},
                keywords={"помята"},
            ),
        ],
    )
    assert selected is not None
    assert selected.code == "film_quality_negative"


def test_positive_rating_with_size_praise_does_not_select_negative_size_template() -> None:
    selected = MatchingService().select_template(
        FeedbackContext(
            wb_feedback_id="f1",
            rating=5,
            pros="Спасибо размеры как надо. Рекомендую",
        ),
        [
            TemplateCandidate(
                1,
                "rating_5_positive",
                "Positive",
                "positive",
                "positive",
                10,
                ratings={5},
            ),
            TemplateCandidate(
                2,
                "size_issue",
                "Size",
                "size",
                "size",
                130,
                ratings={1, 2, 3},
                keywords={"размер"},
            ),
        ],
    )
    assert selected is not None
    assert selected.code == "rating_5_positive"


def test_negative_rating_with_unknown_topic_stays_manual() -> None:
    selected = MatchingService().select_template(
        FeedbackContext(wb_feedback_id="f1", rating=2, review_text="Не понравилось"),
        [
            TemplateCandidate(
                1,
                "packaging",
                "Packaging",
                "packaging",
                "pack",
                100,
                ratings={1, 2, 3},
                keywords={"коробка"},
            ),
            TemplateCandidate(2, "default", "Default", "default", "fallback", 0, is_default=True),
        ],
    )
    assert selected is None


def test_negative_rating_without_text_selects_no_text_template() -> None:
    selected = MatchingService().select_template(
        FeedbackContext(wb_feedback_id="f1", rating=1, review_text=None),
        [
            TemplateCandidate(
                1,
                "negative_no_text",
                "No text",
                "negative_no_text",
                "details",
                20,
                ratings={1, 2, 3},
            ),
            TemplateCandidate(2, "default", "Default", "default", "fallback", 0, is_default=True),
        ],
    )
    assert selected is not None
    assert selected.code == "negative_no_text"


def test_default_fallback_for_non_negative_rating() -> None:
    selected = MatchingService().select_template(
        FeedbackContext(wb_feedback_id="f1", rating=4, review_text="без деталей"),
        [TemplateCandidate(1, "default", "Default", "default", "fallback", 0, is_default=True)],
    )
    assert selected is not None
    assert selected.code == "default"


def test_normalize_feedback_text() -> None:
    assert normalize_feedback_text("Ёлка   помята!", "  Коробка") == "елка помята коробка"


def test_render_preserves_template_line_breaks() -> None:
    text = "{{buyer_greeting}} Спасибо.\nС уважением, команда"
    answer = AnswerRenderer().render(
        text,
        FeedbackContext(wb_feedback_id="f1", rating=5, product_name="Чехол"),
    )
    assert answer == "Здравствуйте! Спасибо.\nС уважением, команда"
