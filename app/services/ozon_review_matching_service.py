import re
from dataclasses import dataclass

from app.services.ozon_review_template_catalog import OzonReviewTemplateCandidate


@dataclass(frozen=True)
class OzonReviewContext:
    ozon_review_id: str
    rating: int
    sku: int | None = None
    product_id: int | None = None
    offer_id: str | None = None
    product_name: str | None = None
    buyer_name: str | None = None
    review_text: str | None = None
    pros: str | None = None
    cons: str | None = None
    has_official_comment: bool = False


class OzonReviewMatchingService:
    def select_template(
        self,
        review: OzonReviewContext,
        templates: list[OzonReviewTemplateCandidate],
    ) -> OzonReviewTemplateCandidate | None:
        if review.has_official_comment:
            return None
        normalized_text = normalize_ozon_review_text(review.review_text, review.pros, review.cons)
        has_text = bool(normalized_text)
        is_negative_rating = review.rating in {1, 2, 3}
        ranked: list[tuple[int, int, OzonReviewTemplateCandidate]] = []
        for template in templates:
            rating_match = review.rating in template.ratings
            offer_match = review.offer_id is not None and review.offer_id in template.offer_ids
            offer_scope = not template.offer_ids or offer_match
            keyword_match = any(keyword in normalized_text for keyword in template.keywords)
            score = self._score(
                template,
                rating_match,
                offer_match,
                offer_scope,
                keyword_match,
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
        template: OzonReviewTemplateCandidate,
        rating_match: bool,
        offer_match: bool,
        offer_scope: bool,
        keyword_match: bool,
        is_negative_rating: bool,
        has_text: bool,
    ) -> int:
        if template.ratings and not rating_match:
            return -1
        if is_negative_rating:
            if not has_text:
                if template.category == "negative_no_text" and rating_match:
                    return 20
                return -1
            if not rating_match or not keyword_match:
                return -1
            if offer_match:
                return 50
            return 30
        if offer_match and keyword_match:
            return 50
        if offer_match and rating_match:
            return 40
        if not template.offer_ids and keyword_match:
            return 30
        if offer_scope and rating_match:
            return 20
        if template.is_default:
            return 0
        return -1

def normalize_ozon_review_text(*parts: str | None) -> str:
    text = " ".join(part for part in parts if part)
    if not text:
        return ""
    value = text.lower().replace("ё", "е")
    value = re.sub(r"[^\w\s-]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value
