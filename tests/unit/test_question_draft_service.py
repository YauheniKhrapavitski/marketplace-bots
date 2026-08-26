from app.services.question_draft_service import QuestionDraftService
from app.services.question_matching_service import QuestionContext


def build_context(text: str, sku: str | None = None) -> QuestionContext:
    return QuestionContext(wb_question_id="q1", question_text=text, supplier_article=sku)


def test_tank_front_lights_question_does_not_answer_about_pillars() -> None:
    draft = QuestionDraftService().build_draft(
        build_context("На передние фары TANK 300 есть?", "TANK_300_sw")
    )

    assert draft.intent in {"FIND_SKU", "UNKNOWN"}
    assert "стойки" not in (draft.answer_text or "").lower()


def test_tank_windshield_pillars_2024_confirmed() -> None:
    draft = QuestionDraftService().build_draft(
        build_context("Подойдут стойки лобового стекла TANK 300 на автомобиль 2024 года?")
    )

    assert draft.confidence == "HIGH"
    assert draft.reason == "exact_fit"
    assert "TANK 300" in (draft.answer_text or "")
    assert "2020-2026" in (draft.answer_text or "")
    assert "2024 год входит в диапазон" in (draft.answer_text or "")


def test_universal_strip_dimension_answer() -> None:
    draft = QuestionDraftService().build_draft(
        build_context("Какой размер 56424_100_30_Spect?", "56424_100_30_Spect")
    )

    assert draft.confidence == "HIGH"
    assert "30×100 см" in (draft.answer_text or "")


def test_vesta_without_element_asks_one_clarifying_question() -> None:
    draft = QuestionDraftService().build_draft(build_context("Подойдет на Весту 2020?"))

    assert draft.intent == "CLARIFY"
    assert "Какой именно элемент нужен" in (draft.answer_text or "")


def test_return_or_wrong_size_uses_service_escalation_template() -> None:
    draft = QuestionDraftService().build_draft(
        build_context("Пришла пленка не того размера, что делать?")
    )

    assert draft.confidence == "BLOCK"
    assert draft.intent == "RETURN_DEFECT"
    assert "номер заказа" in (draft.answer_text or "")


def test_tank_windshield_pillars_2027_rejected() -> None:
    draft = QuestionDraftService().build_draft(
        build_context("Подойдут стойки лобового стекла TANK 300 на автомобиль 2027 года?")
    )

    assert draft.confidence == "HIGH"
    assert draft.reason == "year_out_of_range"
    assert "2027 год находится вне диапазона" in (draft.answer_text or "")


def test_unknown_car_availability_returns_no_lekala() -> None:
    draft = QuestionDraftService().build_draft(
        build_context("Здравствуйте, есть ли у вас лекала на Daewoo Matiz?")
    )

    assert draft.confidence == "HIGH"
    assert draft.intent == "CAR_NOT_IN_CATALOG"
    assert "daewoo matiz" in (draft.answer_text or "").lower()
    assert "лекал в актуальном справочнике нет" in (draft.answer_text or "")


def test_known_car_availability_does_not_return_no_lekala() -> None:
    draft = QuestionDraftService().build_draft(
        build_context("Здравствуйте, есть ли у вас лекала на Lada Granta?")
    )

    assert draft.intent != "CAR_NOT_IN_CATALOG"


def test_current_lada_granta_toner_card_confirms_2019_fit() -> None:
    draft = QuestionDraftService().build_draft(
        build_context(
            "на ладу гранту 2019 года подойдут же",
            "Lada_Granta_2018+_optton50",
        )
    )

    assert draft.confidence == "HIGH"
    assert draft.reason == "exact_fit"
    assert "2018-2023" in (draft.answer_text or "")
    assert "2019 год входит в диапазон" in (draft.answer_text or "")
    assert "не найдено" not in (draft.answer_text or "").lower()
