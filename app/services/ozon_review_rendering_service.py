import re

from app.services.ozon_review_matching_service import OzonReviewContext


class OzonReviewAnswerRenderer:
    def __init__(self, brand_name: str = "", signature: str = "") -> None:
        self._brand_name = brand_name
        self._signature = signature

    def render(self, template_text: str, review: OzonReviewContext) -> str:
        values = {
            "buyer_greeting": self._buyer_greeting(review.buyer_name),
            "buyer_name": review.buyer_name or "",
            "product_name": review.product_name or "товар",
            "brand_name": self._brand_name,
            "rating": str(review.rating),
            "offer_id": review.offer_id or "",
            "signature": self._signature,
        }
        rendered = template_text
        for key, value in values.items():
            rendered = rendered.replace("{{" + key + "}}", value)
        rendered = "\n".join(
            re.sub(r"[^\S\n]+", " ", line).strip()
            for line in rendered.strip().splitlines()
        )
        rendered = re.sub(r"\n{3,}", "\n\n", rendered)
        return rendered.strip()

    @staticmethod
    def _buyer_greeting(name: str | None) -> str:
        clean = (name or "").strip()
        if clean:
            return f"Здравствуйте, {clean}!"
        return "Здравствуйте!"
