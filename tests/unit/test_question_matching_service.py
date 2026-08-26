from app.services.question_matching_service import (
    QuestionContext,
    QuestionMatchingService,
    normalize_question_text,
)
from app.services.question_template_catalog import QuestionTemplateCandidate


def test_selects_film_template_by_keywords() -> None:
    selected = QuestionMatchingService().select_template(
        QuestionContext(wb_question_id="q1", question_text="Какая пленка и сколько микрон?"),
        [
            QuestionTemplateCandidate(
                id=1,
                code="film_request",
                name="Запрос на пленку",
                category="film",
                text="film",
                priority=90,
                keywords={"пленка", "микрон"},
            )
        ],
    )

    assert selected is not None
    assert selected.code == "film_request"


def test_risky_question_stays_manual_even_with_keyword_match() -> None:
    selected = QuestionMatchingService().select_template(
        QuestionContext(wb_question_id="q1", question_text="Можно вернуть заказ? Есть пленка?"),
        [
            QuestionTemplateCandidate(
                id=1,
                code="film_request",
                name="Запрос на пленку",
                category="film",
                text="film",
                priority=90,
                keywords={"пленка"},
            )
        ],
    )

    assert selected is None


def test_unknown_question_stays_manual() -> None:
    selected = QuestionMatchingService().select_template(
        QuestionContext(wb_question_id="q1", question_text="Здравствуйте"),
        [
            QuestionTemplateCandidate(
                id=1,
                code="instruction",
                name="Инструкция",
                category="instruction",
                text="instruction",
                priority=80,
                keywords={"инструкция"},
            )
        ],
    )

    assert selected is None


def test_normalize_question_text_replaces_yo() -> None:
    assert normalize_question_text("Подойдёт ли?") == "подойдет ли"
