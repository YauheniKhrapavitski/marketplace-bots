from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


class PdfFieldTemplate(BaseModel):
    key: str
    label: str
    page_index: int | None = None
    dx: float = 110
    dy: float = -2
    width: float = 260
    height: float = 18
    font_size: float = 9
    clear_existing: bool = True


class AppendixTemplate(BaseModel):
    phrase: str = "Приложение к накладной серии"
    series_dx: float = 84
    number_dx: float = 122
    dy: float = -2
    series_width: float = 30
    number_width: float = 52
    height: float = 16
    font_size: float = 9


class TtnPdfTemplate(BaseModel):
    name: str
    page_width_min: float = 560
    page_width_max: float = 620
    page_height_min: float = 780
    page_height_max: float = 880
    required_phrases: list[str]
    appendix: AppendixTemplate
    fields: list[PdfFieldTemplate]

    def field_by_key(self) -> dict[str, PdfFieldTemplate]:
        return {field.key: field for field in self.fields}


def load_template(path: Path) -> TtnPdfTemplate:
    with path.open("r", encoding="utf-8") as stream:
        return TtnPdfTemplate.model_validate(json.load(stream))
