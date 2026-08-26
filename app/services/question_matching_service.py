import re
from dataclasses import dataclass

from app.services.question_template_catalog import QuestionTemplateCandidate

RISKY_KEYWORDS = {
    "возврат",
    "вернуть",
    "гарантия",
    "гарантии",
    "брак",
    "заказ",
    "доставка",
    "срок доставки",
    "оплата",
    "деньги",
    "компенсация",
    "претензия",
    "жалоба",
}


@dataclass(frozen=True)
class QuestionContext:
    wb_question_id: str
    question_text: str
    nm_id: int | None = None
    imt_id: int | None = None
    product_name: str | None = None
    supplier_article: str | None = None
    brand_name: str | None = None


class QuestionMatchingService:
    def select_template(
        self,
        question: QuestionContext,
        templates: list[QuestionTemplateCandidate],
    ) -> QuestionTemplateCandidate | None:
        normalized_text = normalize_question_text(question.question_text)
        if not normalized_text or self._has_risky_keyword(normalized_text):
            return None
        ranked: list[tuple[int, int, QuestionTemplateCandidate]] = []
        for template in templates:
            product_match = question.nm_id is not None and question.nm_id in template.products
            product_scope = not template.products or product_match
            keyword_matches = sum(1 for keyword in template.keywords if keyword in normalized_text)
            if not product_scope or keyword_matches == 0:
                continue
            score = keyword_matches * 10 + template.priority
            if product_match:
                score += 50
            ranked.append((score, template.priority, template))
        if not ranked:
            return None
        return max(ranked, key=lambda item: (item[0], item[1]))[2]

    @staticmethod
    def _has_risky_keyword(normalized_text: str) -> bool:
        return any(keyword in normalized_text for keyword in RISKY_KEYWORDS)


def normalize_question_text(text: str | None) -> str:
    if not text:
        return ""
    value = text.lower().replace("ё", "е")
    value = re.sub(r"[^\w\s-]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value
