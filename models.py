from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class NomenclatureRow:
    vendor_code: str
    nm_id: int
    title: str


@dataclass(frozen=True, slots=True)
class PriceTemplateRow:
    vendor_code: str
    nm_id: int
    tech_size_name: str
    size_id: int | None
    current_price: float | int | None
    current_discount: float | int | None
    discounted_price: float | int | None
    club_discounted_price: float | int | None
    club_discount: float | int | None
    currency: str
    editable_size_price: bool | None
    is_bad_turnover: bool | None


@dataclass(frozen=True, slots=True)
class ExportData:
    nomenclatures: list[NomenclatureRow]
    prices: list[PriceTemplateRow]


@dataclass(frozen=True, slots=True)
class ApiTokens:
    content: str
    prices: str


class WildberriesExportError(Exception):
    """Safe user-facing error. Do not include secrets in messages."""


class WildberriesApiError(WildberriesExportError):
    def __init__(self, report_name: str, status_code: int, message: str) -> None:
        super().__init__(f"{report_name}: {message}")
        self.report_name = report_name
        self.status_code = status_code


JsonObject = dict[str, Any]
