import re
from dataclasses import dataclass, field

from app.services.question_catalog import (
    CATALOG_VERSION,
    ProductCatalog,
    ProductCatalogItem,
    load_product_catalog,
    normalize_model,
    normalize_sku,
    normalize_text,
    select_year_range,
)
from app.services.question_matching_service import QuestionContext


@dataclass(frozen=True)
class QuestionDraft:
    answer_text: str | None
    status: str
    confidence: str
    intent: str
    reason: str
    extracted: dict[str, object] = field(default_factory=dict)
    matched_skus: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractedQuestion:
    brand: str | None
    model: str | None
    year: int | None
    element: str | None


def _model_family_tokens(model: str) -> set[str]:
    stop_words = {
        "cross",
        "hatchback",
        "liftback",
        "sedan",
        "sport",
        "sw",
        "universal",
        "год",
        "года",
        "дорест",
        "лифтбек",
        "рест",
        "рестайлинг",
        "седан",
        "универсал",
        "хэтч",
        "хэтчбек",
    }
    return {
        token
        for token in re.findall(r"[a-zа-я0-9]+", normalize_model(model))
        if len(token) > 1 and not token.isdigit() and token not in stop_words
    }


class QuestionDraftService:
    def __init__(self, catalog: ProductCatalog | None = None) -> None:
        self._catalog = catalog or load_product_catalog()

    def build_draft(self, question: QuestionContext) -> QuestionDraft:
        current_item = self._catalog.get_by_sku(question.supplier_article)
        extracted = self._extract(question.question_text, current_item)
        text_norm = normalize_text(question.question_text)

        block = self._block_reason(text_norm)
        if block:
            return QuestionDraft(
                answer_text=self._service_answer(block),
                status="manual",
                confidence="BLOCK",
                intent=block,
                reason="mandatory_escalation",
                extracted=self._payload(extracted),
            )

        if self._is_dimension_question(text_norm):
            return self._dimension_answer(question, current_item)

        if self._is_instruction_question(text_norm):
            element = extracted.element or (current_item.element if current_item else "товар")
            return QuestionDraft(
                answer_text=(
                    f"Здравствуйте! Инструкция по установке для элемента «{element}» "
                    "доступна по QR-коду на вкладыше в упаковке. Если QR-код не открывается, "
                    "передаем вопрос специалисту."
                ),
                status="pending",
                confidence="MEDIUM",
                intent="INSTALL_VIDEO",
                reason="generic_instruction",
                extracted=self._payload(extracted),
            )

        if self._is_material_question(text_norm):
            return QuestionDraft(
                answer_text=(
                    "Здравствуйте! В актуальной базе нет подтвержденной характеристики "
                    "материала для этого артикула. Передаю вопрос специалисту."
                ),
                status="manual",
                confidence="LOW",
                intent="MATERIAL",
                reason="material_characteristic_missing",
                extracted=self._payload(extracted),
            )

        unavailable = self._unavailable_car_answer(text_norm, extracted)
        if unavailable is not None:
            return unavailable

        if self._is_list_or_sku_question(text_norm):
            return self._list_answer(extracted)

        if self._is_fit_question(text_norm):
            return self._fit_answer(extracted, current_item)

        return QuestionDraft(
            answer_text=(
                "Здравствуйте! Точной информации в актуальной базе нет. "
                "Передаю вопрос специалисту."
            ),
            status="manual",
            confidence="LOW",
            intent="UNKNOWN",
            reason="intent_not_recognized",
            extracted=self._payload(extracted),
        )

    def _fit_answer(
        self, extracted: ExtractedQuestion, current_item: ProductCatalogItem | None
    ) -> QuestionDraft:
        brand = extracted.brand or (current_item.brand if current_item else None)
        model = extracted.model or (current_item.model if current_item else None)
        element = extracted.element or (current_item.element if current_item else None)
        use_current_item = bool(
            current_item and self._is_current_item_fit_check(extracted, current_item)
        )
        if use_current_item and current_item:
            brand = current_item.brand
            model = current_item.model
            element = current_item.element
        if not brand or not model:
            return self._clarify("Уточните, пожалуйста, марку, модель и точный год автомобиля.")
        if extracted.year is None:
            return self._clarify("Уточните, пожалуйста, точный год выпуска автомобиля.")
        if not element:
            return self._clarify(
                "Какой именно элемент нужен: капот, крыша, фары, пороги или стойки?"
            )

        candidates = (
            [current_item]
            if use_current_item and current_item
            else self._catalog.find(brand=brand, model=model, element=element, year=None)
        )
        if not candidates:
            return QuestionDraft(
                answer_text=(
                    f"Здравствуйте! Точной позиции для {brand} {model} и элемента "
                    f"«{element}» в актуальном справочнике не найдено."
                ),
                status="manual",
                confidence="LOW",
                intent="FIT_EXACT",
                reason="no_matching_product",
                extracted=self._payload(extracted),
            )
        best = candidates[0]
        year_range = select_year_range(best, model)
        if year_range is None and not best.is_universal:
            return QuestionDraft(
                answer_text=(
                    "Здравствуйте! Точной информации в актуальной базе нет. "
                    "Передаю вопрос специалисту."
                ),
                status="manual",
                confidence="LOW",
                intent="FIT_EXACT",
                reason="empty_or_unparsed_year_range",
                extracted=self._payload(extracted),
                matched_skus=[best.seller_sku],
            )
        if year_range and not year_range.contains(extracted.year):
            return QuestionDraft(
                answer_text=(
                    f"Для {best.brand} {best.model} указан диапазон {year_range.label}. "
                    f"{extracted.year} год находится вне диапазона, поэтому совместимость "
                    "не подтверждена. Можем помочь подобрать другой артикул."
                ),
                status="pending",
                confidence="HIGH",
                intent="FIT_EXACT",
                reason="year_out_of_range",
                extracted=self._payload(extracted),
                matched_skus=[best.seller_sku],
            )
        return QuestionDraft(
            answer_text=(
                f"Да, лекало предназначено для {best.brand} {best.model} "
                f"{year_range.label if year_range else ''}. Указанный {extracted.year} год "
                f"входит в диапазон. Элемент: {best.element}."
            ),
            status="pending",
            confidence="HIGH",
            intent="FIT_EXACT",
            reason="exact_fit",
            extracted=self._payload(extracted),
            matched_skus=[best.seller_sku],
        )

    @staticmethod
    def _is_current_item_fit_check(
        extracted: ExtractedQuestion, current_item: ProductCatalogItem
    ) -> bool:
        if not extracted.brand or normalize_text(extracted.brand) != normalize_text(
            current_item.brand
        ):
            return False
        if not extracted.model:
            return True
        extracted_model = normalize_model(extracted.model)
        current_model = normalize_model(current_item.model)
        if extracted_model in current_model or current_model in extracted_model:
            return True
        return bool(
            _model_family_tokens(extracted_model) & _model_family_tokens(current_model)
        )

    def _list_answer(self, extracted: ExtractedQuestion) -> QuestionDraft:
        if not extracted.brand or not extracted.model:
            return self._clarify("Уточните марку, модель, точный год выпуска и нужный элемент.")
        if extracted.year is None and not extracted.element:
            return self._clarify("Уточните, пожалуйста, точный год выпуска автомобиля.")
        products = self._catalog.find(
            brand=extracted.brand,
            model=extracted.model,
            element=extracted.element,
            year=extracted.year,
        )
        confirmed = [
            item
            for item in products
            if item.is_universal
            or (
                extracted.year is None
                or (
                    (year_range := select_year_range(item, extracted.model)) is not None
                    and year_range.contains(extracted.year)
                )
            )
        ][:5]
        if not confirmed:
            car = f"{extracted.brand} {extracted.model}"
            year_text = f" {extracted.year} года" if extracted.year else ""
            element_text = f" и элемента «{extracted.element}»" if extracted.element else ""
            return QuestionDraft(
                answer_text=(
                    f"Здравствуйте! Точной позиции для {car}{year_text}{element_text} "
                    "в актуальном справочнике не найдено. "
                    "Передаю запрос на ручной подбор."
                ),
                status="manual",
                confidence="LOW",
                intent="FIND_SKU",
                reason="no_confirmed_product",
                extracted=self._payload(extracted),
            )
        sku_list = "; ".join(f"{item.element} — {item.seller_sku}" for item in confirmed)
        return QuestionDraft(
            answer_text=(
                f"Здравствуйте! Для {extracted.brand} {extracted.model} "
                f"{extracted.year or ''} "
                f"найдено: {sku_list}."
            ),
            status="pending",
            confidence="MEDIUM" if len(confirmed) > 1 else "HIGH",
            intent="FIND_SKU",
            reason="products_found",
            extracted=self._payload(extracted),
            matched_skus=[item.seller_sku for item in confirmed],
        )

    def _unavailable_car_answer(
        self, text_norm: str, extracted: ExtractedQuestion
    ) -> QuestionDraft | None:
        if not self._is_lekala_availability_question(text_norm):
            return None
        brand, model = self._requested_car_for_availability(text_norm, extracted)
        if not brand or not model:
            return None
        if self._catalog_has_brand_model(brand, model):
            return None
        return QuestionDraft(
            answer_text=(
                f"Здравствуйте! Для {brand} {model} лекал в актуальном справочнике нет."
            ),
            status="pending",
            confidence="HIGH",
            intent="CAR_NOT_IN_CATALOG",
            reason="brand_model_not_found_in_catalog",
            extracted={
                "brand": brand,
                "model": model,
                "year": extracted.year,
                "element": extracted.element,
                "catalog_version": CATALOG_VERSION,
            },
        )

    def _requested_car_for_availability(
        self, text_norm: str, extracted: ExtractedQuestion
    ) -> tuple[str | None, str | None]:
        matches = re.findall(
            r"(?:на|для)\s+([a-zа-я0-9-]+)(?:\s+([a-zа-я0-9-]+))?",
            text_norm,
        )
        if not matches:
            return extracted.brand, extracted.model
        raw_brand, raw_model = matches[-1]
        if raw_model:
            return raw_brand, raw_model
        if extracted.brand and extracted.model:
            return extracted.brand, extracted.model
        brand = extracted.brand or raw_brand
        model = extracted.model or raw_model
        if model is None and extracted.brand:
            model = raw_model or raw_brand
        if not extracted.brand:
            brand = raw_brand
        return brand, model

    def _catalog_has_brand_model(self, brand: str, model: str) -> bool:
        brand_norm = normalize_text(brand)
        model_norm = normalize_model(model)
        for item in self._catalog.items:
            if normalize_text(item.brand) != brand_norm:
                continue
            item_model = normalize_model(item.model)
            if model_norm in item_model or item_model in model_norm:
                return True
        return False

    def _dimension_answer(
        self, question: QuestionContext, current_item: ProductCatalogItem | None
    ) -> QuestionDraft:
        item = current_item or self._extract_sku_item(question.question_text)
        if item is None:
            return self._clarify("Уточните, пожалуйста, артикул товара.")
        dimension = self._extract_dimension(item)
        if not dimension:
            return QuestionDraft(
                answer_text=(
                    "Здравствуйте! Точные размеры этого лекала в базе не указаны. "
                    "Чтобы не вводить вас в заблуждение, передаю вопрос специалисту."
                ),
                status="manual",
                confidence="LOW",
                intent="DIMENSIONS",
                reason="dimension_missing",
                matched_skus=[item.seller_sku],
            )
        return QuestionDraft(
            answer_text=(
                f"Здравствуйте! Размер товара {item.seller_sku}: {dimension}. "
                f"Товар предназначен для {item.element}."
            ),
            status="pending",
            confidence="HIGH",
            intent="DIMENSIONS",
            reason="dimension_from_catalog",
            matched_skus=[item.seller_sku],
        )

    def _extract(
        self, question_text: str, current_item: ProductCatalogItem | None
    ) -> ExtractedQuestion:
        text_norm = normalize_text(question_text)
        brand = self._extract_brand(text_norm)
        model = self._extract_model(text_norm, brand)
        if model and not brand:
            brand = self._brand_for_model(model)
        year = self._extract_year(text_norm)
        element = self._extract_element(text_norm)
        if current_item and not brand and self._looks_like_current_product_question(text_norm):
            brand = current_item.brand
            model = current_item.model
        return ExtractedQuestion(brand=brand, model=model, year=year, element=element)

    def _brand_for_model(self, model: str) -> str | None:
        model_norm = normalize_text(model)
        for item in self._catalog.items:
            if normalize_text(item.model) == model_norm:
                return item.brand
        return None

    def _extract_brand(self, text_norm: str) -> str | None:
        brand_aliases = {
            "tank": ("tank", "танк"),
            "geely": ("geely", "джили"),
            "belgee": ("belgee", "белджи"),
            "lada": ("lada", "лада", "ладу", "ладе"),
            "skoda": ("skoda", "шкода"),
            "audi": ("audi", "ауди"),
            "bmw": ("bmw", "бмв"),
            "chery": ("chery", "chery", "чери", "черри"),
            "haval": ("haval", "хавал"),
            "jetour": ("jetour", "джетур"),
            "renault": ("renault", "рено"),
        }
        for item in self._catalog.items:
            aliases = brand_aliases.get(normalize_text(item.brand), (normalize_text(item.brand),))
            if any(alias and alias in text_norm for alias in aliases):
                return item.brand
        return None

    def _extract_model(self, text_norm: str, brand: str | None) -> str | None:
        model_aliases = {
            "vesta": ("vesta", "веста", "весту", "весте"),
            "granta": ("granta", "гранта", "гранту", "гранте"),
            "coolray": ("coolray", "кулрей", "coolray"),
            "300": ("300",),
            "atlas": ("atlas", "атлас"),
            "atlas pro": ("atlas pro", "атлас про"),
        }
        candidates = [
            item.model
            for item in self._catalog.items
            if item.model and (brand is None or normalize_text(item.brand) == normalize_text(brand))
        ]
        candidates.sort(key=len, reverse=True)
        for canonical, aliases in model_aliases.items():
            if not any(alias and alias in text_norm for alias in aliases):
                continue
            for model in candidates:
                if canonical in normalize_model(model):
                    return model
        for model in candidates:
            model_norm = normalize_text(re.sub(r"\b(19|20)\d{2}\+?\b", " ", model))
            parts = [part.strip() for part in re.split(r"[/+]", model_norm) if part.strip()]
            search_aliases = [
                alias
                for part in parts + [model_norm]
                for alias in model_aliases.get(part, (part,))
                if len(alias) > 1
            ]
            if any(alias and alias in text_norm for alias in search_aliases):
                return model
        return None

    @staticmethod
    def _extract_year(text_norm: str) -> int | None:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", text_norm)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_element(text_norm: str) -> str | None:
        groups = {
            "передние фары": ("передние фары", "фары", "оптика"),
            "задние фонари": ("задние фонари", "задние фары", "фонари"),
            "стойки лобового стекла": ("стойки лобового", "передние стойки"),
            "стойки боковые на двери": ("стойки двер", "стойки боков"),
            "капот": ("капот",),
            "крыша": ("крыша", "крышу"),
            "пороги": ("порог",),
            "полка заднего бампера": ("задний бампер", "полка"),
            "передний бампер": ("передний бампер", "бампер"),
            "антиманикюр": ("ручк", "антиманикюр"),
            "экран мультимедиа": ("экран", "монитор", "мультимедиа"),
        }
        for element, keywords in groups.items():
            if any(keyword in text_norm for keyword in keywords):
                return element
        return None

    @staticmethod
    def _looks_like_current_product_question(text_norm: str) -> bool:
        return any(
            word in text_norm for word in ("подойдет", "подоидет", "подходит", "данная", "этот")
        )

    @staticmethod
    def _block_reason(text_norm: str) -> str | None:
        rules = {
            "DELIVERY": ("доставка", "доставят", "отправить", "статус заказа", "переносится"),
            "RETURN_DEFECT": (
                "возврат",
                "вернуть",
                "брак",
                "не подошла",
                "не подошло",
                "не того размера",
                "пузыри",
                "залом",
                "обман",
            ),
            "WRONG_MISSING": ("не хватает", "недокомплект", "пришла не", "другой товар"),
            "PRICE": ("скидк", "цена", "стоимость"),
        }
        for intent, keywords in rules.items():
            if any(keyword in text_norm for keyword in keywords):
                return intent
        return None

    @staticmethod
    def _service_answer(intent: str) -> str:
        if intent == "DELIVERY":
            return (
                "Здравствуйте! Мы не видим точную логистику заказа в этом чате. "
                "Проверьте статус в приложении Wildberries; при просрочке обратитесь "
                "в поддержку Wildberries по заказу."
            )
        if intent == "WRONG_MISSING":
            return (
                "Здравствуйте! Состав комплекта нужно проверить по вашему заказу. "
                "Пришлите номер заказа и фото полученного товара."
            )
        if intent == "PRICE":
            return (
                "Здравствуйте! Цена и скидка могут меняться на Wildberries; "
                "актуальная стоимость указана в карточке товара."
            )
        return (
            "Здравствуйте! Сожалеем, что возникла проблема. Пожалуйста, пришлите "
            "номер заказа, фото пленки или упаковки и укажите автомобиль, год и элемент. "
            "Передаем обращение специалисту."
        )

    @staticmethod
    def _is_fit_question(text_norm: str) -> bool:
        return any(word in text_norm for word in ("подойдет", "подоидет", "подходит", "на "))

    @staticmethod
    def _is_list_or_sku_question(text_norm: str) -> bool:
        return any(
            word in text_norm for word in ("артикул", "есть", "найти", "скиньте", "комплект")
        )

    @staticmethod
    def _is_lekala_availability_question(text_norm: str) -> bool:
        return (
            any(word in text_norm for word in ("есть", "имеется", "наличии", "делаете"))
            and any(word in text_norm for word in ("лекал", "пленк", "плёнк"))
            and any(word in text_norm for word in (" на ", " для "))
        )

    @staticmethod
    def _is_dimension_question(text_norm: str) -> bool:
        return any(word in text_norm for word in ("размер", "длина", "ширина", "сколько см"))

    @staticmethod
    def _is_material_question(text_norm: str) -> bool:
        return any(
            word in text_norm
            for word in (
                "полиуретан",
                "гибрид",
                "толщина",
                "микрон",
                "производитель",
                "срок службы",
            )
        )

    @staticmethod
    def _is_instruction_question(text_norm: str) -> bool:
        return any(word in text_norm for word in ("инструкция", "видео", "qr", "как клеить"))

    def _extract_sku_item(self, question_text: str) -> ProductCatalogItem | None:
        text_norm = normalize_sku(question_text)
        for sku, item in self._catalog.by_sku.items():
            if sku in text_norm:
                return item
        return None

    @staticmethod
    def _extract_dimension(item: ProductCatalogItem) -> str | None:
        source = f"{item.seller_sku} {item.element} {item.comment}"
        match = re.search(r"(\d+(?:[,.]\d+)?)\s*[xх]\s*(\d+(?:[,.]\d+)?)\s*(см|м)?", source, re.I)
        if not match:
            return None
        left = match.group(1).replace(".", ",")
        right = match.group(2).replace(".", ",")
        unit = match.group(3) or "см"
        return f"{left}×{right} {unit}"

    @staticmethod
    def _payload(extracted: ExtractedQuestion) -> dict[str, object]:
        return {
            "brand": extracted.brand,
            "model": extracted.model,
            "year": extracted.year,
            "element": extracted.element,
            "catalog_version": CATALOG_VERSION,
        }

    @staticmethod
    def _clarify(text: str) -> QuestionDraft:
        return QuestionDraft(
            answer_text=text,
            status="manual",
            confidence="MEDIUM",
            intent="CLARIFY",
            reason="missing_required_parameter",
        )
