from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path

import fitz
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from ttn_bot.models import TtnEditData
from ttn_bot.template import PdfFieldTemplate, TtnPdfTemplate


class PdfFillError(RuntimeError):
    pass


_REGISTERED_FONTS: set[str] = set()


def fill_pdf(
    source_pdf: Path,
    output_pdf: Path,
    data: TtnEditData,
    template: TtnPdfTemplate,
    font_path: Path,
) -> None:
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_pdf, output_pdf)
    document = fitz.open(output_pdf)
    try:
        font_name = "ttn_font"
        use_custom_font = font_path.exists()

        for field in template.fields:
            value = _value_for_field(data, field.key)
            _fill_field(document, field, value, font_name, font_path, use_custom_font)

        _fill_appendices(
            document,
            data,
            template,
            font_name,
            font_path,
            use_custom_font,
        )
        document.saveIncr()
    finally:
        document.close()


def _fill_field(
    document: fitz.Document,
    field: PdfFieldTemplate,
    value: str,
    font_name: str,
    font_path: Path,
    use_custom_font: bool,
) -> None:
    pages = [document[field.page_index]] if field.page_index is not None else list(document)
    for page in pages:
        matches = _find_label_rects(page, field.label)
        if not matches:
            continue
        label_rect = matches[0]
        target = fitz.Rect(
            label_rect.x0 + field.dx,
            label_rect.y0 + field.dy,
            label_rect.x0 + field.dx + field.width,
            label_rect.y0 + field.dy + field.height,
        )
        _write_text(
            page,
            target,
            value,
            field.font_size,
            font_name,
            font_path,
            use_custom_font,
            field.clear_existing,
        )
        return
    raise PdfFillError(f"Не найдено поле PDF: {field.label}")


def _fill_appendices(
    document: fitz.Document,
    data: TtnEditData,
    template: TtnPdfTemplate,
    font_name: str,
    font_path: Path,
    use_custom_font: bool,
) -> None:
    filled = 0
    appendix = template.appendix
    for page in document:
        for label_rect in _find_label_rects(page, appendix.phrase):
            series_target = fitz.Rect(
                label_rect.x0 + appendix.series_dx,
                label_rect.y0 + appendix.dy,
                label_rect.x0 + appendix.series_dx + appendix.series_width,
                label_rect.y0 + appendix.dy + appendix.height,
            )
            number_target = fitz.Rect(
                label_rect.x0 + appendix.number_dx,
                label_rect.y0 + appendix.dy,
                label_rect.x0 + appendix.number_dx + appendix.number_width,
                label_rect.y0 + appendix.dy + appendix.height,
            )
            _write_text(
                page,
                series_target,
                data.ttn_series,
                appendix.font_size,
                font_name,
                font_path,
                use_custom_font,
                True,
            )
            _write_text(
                page,
                number_target,
                data.ttn_number,
                appendix.font_size,
                font_name,
                font_path,
                use_custom_font,
                True,
            )
            filled += 1
    if filled == 0:
        raise PdfFillError("Не найдены страницы приложений для заполнения серии и номера")


def _write_text(
    page: fitz.Page,
    rect: fitz.Rect,
    value: str,
    font_size: float,
    font_name: str,
    font_path: Path,
    use_custom_font: bool,
    clear_existing: bool,
) -> None:
    packet = BytesIO()
    page_width = float(page.rect.width)
    page_height = float(page.rect.height)
    pdf = canvas.Canvas(packet, pagesize=(page_width, page_height))

    if clear_existing:
        pdf.setFillColorRGB(1, 1, 1)
        pdf.setStrokeColorRGB(1, 1, 1)
        pdf.rect(
            rect.x0,
            page_height - rect.y1,
            rect.width,
            rect.height,
            stroke=0,
            fill=1,
        )

    if use_custom_font:
        _register_reportlab_font(font_name, font_path)
        pdf.setFont(font_name, font_size)
    else:
        pdf.setFont("Helvetica", font_size)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.drawString(rect.x0, page_height - rect.y0 - font_size, value)
    pdf.save()

    overlay_pdf = fitz.open("pdf", packet.getvalue())
    try:
        page.show_pdf_page(page.rect, overlay_pdf, 0, overlay=True)
    finally:
        overlay_pdf.close()


def _register_reportlab_font(font_name: str, font_path: Path) -> None:
    if font_name in _REGISTERED_FONTS:
        return
    pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    _REGISTERED_FONTS.add(font_name)


def _find_label_rects(page: fitz.Page, label: str) -> list[fitz.Rect]:
    matches: list[fitz.Rect] = list(page.search_for(label))
    if matches:
        return matches

    label_words = label.split()
    words = page.get_text("words")
    rects: list[fitz.Rect] = []
    for index in range(0, len(words) - len(label_words) + 1):
        if all(words[index + offset][4] == word for offset, word in enumerate(label_words)):
            x0 = min(words[index + offset][0] for offset in range(len(label_words)))
            y0 = min(words[index + offset][1] for offset in range(len(label_words)))
            x1 = max(words[index + offset][2] for offset in range(len(label_words)))
            y1 = max(words[index + offset][3] for offset in range(len(label_words)))
            rects.append(fitz.Rect(x0, y0, x1, y1))
    return rects


def _value_for_field(data: TtnEditData, key: str) -> str:
    if key == "series_and_number":
        return data.series_and_number
    value = getattr(data, key, None)
    if not isinstance(value, str):
        raise PdfFillError(f"Неизвестное поле шаблона: {key}")
    return value
