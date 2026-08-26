from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass(frozen=True)
class ExtractedItem:
    row_number: int
    name: str
    quantity: str | None = None
    unit: str | None = None
    price: str | None = None
    amount: str | None = None


@dataclass(frozen=True)
class ExtractedTtnData:
    text: str
    items: list[ExtractedItem]
    tables: list[list[list[str | None]]]


def extract_ttn_data(path: Path) -> ExtractedTtnData:
    texts: list[str] = []
    items: list[ExtractedItem] = []
    tables: list[list[list[str | None]]] = []
    row_number = 1

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            texts.append(page_text)
            for table in page.extract_tables() or []:
                if table:
                    tables.append(table)
                for row in table:
                    item = _row_to_item(row, row_number)
                    if item is None:
                        continue
                    items.append(item)
                    row_number += 1

    return ExtractedTtnData(text="\n".join(texts), items=items, tables=tables)


def _row_to_item(row: list[str | None], row_number: int) -> ExtractedItem | None:
    cells = [_clean_cell(cell) for cell in row]
    cells = [cell for cell in cells if cell]
    if len(cells) < 2:
        return None
    joined_lower = " ".join(cells).lower()
    if any(marker in joined_lower for marker in ("наименование", "количество", "товарный раздел")):
        return None

    name_index = 1 if cells[0].isdigit() and len(cells) > 1 else 0
    name = cells[name_index]
    if len(name) < 2:
        return None

    rest = cells[name_index + 1 :]
    return ExtractedItem(
        row_number=row_number,
        name=name,
        quantity=rest[0] if len(rest) > 0 else None,
        unit=rest[1] if len(rest) > 1 else None,
        price=rest[2] if len(rest) > 2 else None,
        amount=rest[3] if len(rest) > 3 else None,
    )


def _clean_cell(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.replace("\n", " ").split())
