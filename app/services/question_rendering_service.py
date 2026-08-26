import re

from app.services.question_matching_service import QuestionContext


class QuestionAnswerRenderer:
    def render(self, template_text: str, question: QuestionContext) -> str:
        values = {
            "product_name": question.product_name or "товар",
            "article": question.supplier_article or "",
            "brand_name": question.brand_name or "",
        }
        rendered = template_text
        for key, value in values.items():
            rendered = rendered.replace("{{" + key + "}}", value)
        rendered = "\n".join(
            re.sub(r"[^\S\n]+", " ", line).strip() for line in rendered.strip().splitlines()
        )
        return re.sub(r"\n{3,}", "\n\n", rendered)
