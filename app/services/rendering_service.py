import re

from app.services.matching_service import FeedbackContext


class AnswerRenderer:
    def __init__(self, brand_name: str = "", signature: str = "") -> None:
        self._brand_name = brand_name
        self._signature = signature

    def render(self, template_text: str, feedback: FeedbackContext) -> str:
        values = {
            "buyer_greeting": self._buyer_greeting(feedback.buyer_name),
            "buyer_name": feedback.buyer_name or "",
            "product_name": feedback.product_name or "товар",
            "brand_name": self._brand_name,
            "rating": str(feedback.rating),
            "article": feedback.supplier_article or "",
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
        rendered = rendered.replace(" ,", ",").replace(" !", "!")
        return rendered

    @staticmethod
    def _buyer_greeting(name: str | None) -> str:
        clean = (name or "").strip()
        if clean:
            return f"Здравствуйте, {clean}!"
        return "Здравствуйте!"
