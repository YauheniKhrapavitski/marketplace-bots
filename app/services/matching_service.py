import re
from dataclasses import dataclass

from app.services.template_catalog import TemplateCandidate


@dataclass(frozen=True)
class FeedbackContext:
    wb_feedback_id: str
    rating: int
    nm_id: int | None = None
    product_name: str | None = None
    buyer_name: str | None = None
    review_text: str | None = None
    pros: str | None = None
    cons: str | None = None
    supplier_article: str | None = None


class MatchingService:
    def select_template(
        self,
        feedback: FeedbackContext,
        templates: list[TemplateCandidate],
    ) -> TemplateCandidate | None:
        active = templates
        normalized_text = normalize_feedback_text(
            feedback.review_text, feedback.pros, feedback.cons
        )
        has_text = bool(normalized_text)
        is_negative_rating = feedback.rating in {1, 2, 3}
        ranked: list[tuple[int, int, TemplateCandidate]] = []
        for template in active:
            product_match = feedback.nm_id is not None and feedback.nm_id in template.products
            product_scope = not template.products or product_match
            keyword_match = any(keyword in normalized_text for keyword in template.keywords)
            rating_match = feedback.rating in template.ratings
            score = self._score(
                template,
                product_match,
                product_scope,
                keyword_match,
                rating_match,
                is_negative_rating,
                has_text,
            )
            if score >= 0:
                ranked.append((score, template.priority, template))
        if not ranked:
            return None
        return max(ranked, key=lambda item: (item[0], item[1]))[2]

    @staticmethod
    def _score(
        template: TemplateCandidate,
        product_match: bool,
        product_scope: bool,
        keyword_match: bool,
        rating_match: bool,
        is_negative_rating: bool,
        has_text: bool,
    ) -> int:
        if template.ratings and not rating_match:
            return -1
        if is_negative_rating:
            if template.category == "negative_no_text" and rating_match:
                return 100
            if not has_text:
                return -1
            if not rating_match:
                return -1
            if not keyword_match:
                if template.category == "negative_no_text":
                    return 5
                return -1
            if product_match:
                return 50
            return 30
        if product_match and keyword_match:
            return 50
        if product_match and rating_match:
            return 40
        if not template.products and keyword_match:
            return 30
        if product_scope and rating_match:
            return 20
        if template.is_default:
            return 0
        return -1


def normalize_feedback_text(*parts: str | None) -> str:
    text = " ".join(part for part in parts if part)
    text = text.lower().replace("ё", "е")
    text = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text
