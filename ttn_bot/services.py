from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

from ttn_bot.excel import validate_excel, write_ttn_excel
from ttn_bot.models import TtnEditData
from ttn_bot.pdf.editor import fill_pdf
from ttn_bot.pdf.extractor import extract_ttn_data
from ttn_bot.pdf.validator import validate_pdf
from ttn_bot.storage import Storage
from ttn_bot.template import TtnPdfTemplate


@dataclass(frozen=True)
class JobResult:
    filled_pdf: Path
    excel: Path


def process_ttn_job(
    job_id: str,
    job_dir: Path,
    source_pdf: Path,
    edit_data: TtnEditData,
    template: TtnPdfTemplate,
    font_path: Path,
    storage: Storage,
) -> JobResult:
    storage.update_job(job_id, "processing")
    validate_pdf(source_pdf, template)

    output_pdf = job_dir / _filled_pdf_file_name(source_pdf)
    output_excel = job_dir / _excel_file_name(source_pdf)

    fill_pdf(source_pdf, output_pdf, edit_data, template, font_path)
    _validate_filled_pdf(output_pdf, edit_data)

    extracted = extract_ttn_data(output_pdf)
    write_ttn_excel(output_excel, edit_data, extracted)
    validate_excel(output_excel)

    storage.update_job(job_id, "done")
    return JobResult(filled_pdf=output_pdf, excel=output_excel)


def _validate_filled_pdf(path: Path, edit_data: TtnEditData) -> None:
    if not path.exists() or path.stat().st_size == 0:
        raise ValueError("Заполненный PDF не был создан")
    with fitz.open(path) as document:
        text = "\n".join(page.get_text("text") for page in document)
    if edit_data.ttn_series not in text or edit_data.ttn_number not in text:
        raise ValueError("Не удалось проверить серию и номер в заполненном PDF")


def _filled_pdf_file_name(source_pdf: Path) -> str:
    return f"{source_pdf.stem} заполненный{source_pdf.suffix}"


def _excel_file_name(source_pdf: Path) -> str:
    return f"{source_pdf.stem}.xlsx"
