from pathlib import Path

import fitz

from ttn_bot.models import TtnEditData
from ttn_bot.pdf.editor import fill_pdf
from ttn_bot.pdf.validator import validate_pdf
from ttn_bot.services import _excel_file_name, _filled_pdf_file_name
from ttn_bot.template import TtnPdfTemplate, load_template


def test_validate_and_fill_pdf(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "filled.pdf"
    template = load_template(Path("config/ttn_templates/ozon_ttn_a4.json"))
    _create_sample_ttn_pdf(source, template)
    data = TtnEditData(
        vehicle="Газель NN ВА9712-7",
        driver="Мартиневский Иван Васильевич",
        ttn_series="ЕМ",
        ttn_number="1926709",
        goods_accepted_by="Мартиневский Иван Васильевич",
        release_allowed_by="Китасов А.С.",
        shipper_handed_over_by="Китасов А.С.",
    )

    result = validate_pdf(source, template)
    fill_pdf(source, output, data, template, Path("assets/fonts/DejaVuSans.ttf"))

    assert result.page_count == 2
    with fitz.open(output) as document:
        text = "\n".join(page.get_text("text") for page in document)
    assert "ЕМ" in text
    assert "1926709" in text
    assert "Газель NN ВА9712-7" in text


def test_filled_pdf_file_name_uses_source_name() -> None:
    assert _filled_pdf_file_name(Path("117682617.pdf")) == "117682617 заполненный.pdf"


def test_excel_file_name_uses_source_name() -> None:
    assert _excel_file_name(Path("117682617.pdf")) == "117682617.xlsx"


def _create_sample_ttn_pdf(path: Path, template: TtnPdfTemplate) -> None:
    document = fitz.open()
    font_path = Path("assets/fonts/DejaVuSans.ttf")
    page = document.new_page(width=595, height=842)
    lines = [
        "ТОВАРНЫЙ РАЗДЕЛ",
        "Автомобиль",
        "Водитель",
        "Отпуск разрешил",
        "Сдал грузоотправитель",
        "Товар к перевозке принял",
    ]
    y = 60
    for line in lines:
        page.insert_text((60, y), line, fontsize=10, fontname="dejavu", fontfile=str(font_path))
        y += 28
    appendix = document.new_page(width=595, height=842)
    appendix.insert_text(
        (60, 60),
        template.appendix.phrase,
        fontsize=10,
        fontname="dejavu",
        fontfile=str(font_path),
    )
    document.save(path)
    document.close()
