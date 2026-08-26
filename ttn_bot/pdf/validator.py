from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

from ttn_bot.template import TtnPdfTemplate


class PdfValidationError(ValueError):
    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass(frozen=True)
class PdfValidationResult:
    page_count: int
    first_page_width: float
    first_page_height: float


SCAN_MESSAGE = (
    "Документ не содержит текстового слоя. Сканированные документы пока не поддерживаются"
)
UNKNOWN_FORMAT_MESSAGE = (
    "Этот формат ТТН пока не поддерживается. Требуется настройка шаблона документа"
)


def validate_pdf(path: Path, template: TtnPdfTemplate) -> PdfValidationResult:
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise PdfValidationError("PDF не открывается. Загрузите корректный файл PDF") from exc

    with document:
        if document.page_count < 1:
            raise PdfValidationError("PDF не содержит страниц")

        texts = [page.get_text("text") for page in document]
        if not any(text.strip() for text in texts):
            raise PdfValidationError(SCAN_MESSAGE)

        first_rect = document[0].rect
        if not (
            template.page_width_min <= first_rect.width <= template.page_width_max
            and template.page_height_min <= first_rect.height <= template.page_height_max
        ):
            raise PdfValidationError(UNKNOWN_FORMAT_MESSAGE)

        full_text = "\n".join(texts)
        if any(phrase not in full_text for phrase in template.required_phrases):
            raise PdfValidationError(UNKNOWN_FORMAT_MESSAGE)

        if template.appendix.phrase not in full_text:
            raise PdfValidationError(UNKNOWN_FORMAT_MESSAGE)

        return PdfValidationResult(
            page_count=document.page_count,
            first_page_width=first_rect.width,
            first_page_height=first_rect.height,
        )
