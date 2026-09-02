from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator


class TtnEditData(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    vehicle: str
    driver: str
    ttn_series: str
    ttn_number: str
    goods_accepted_by: str
    release_allowed_by: str
    shipper_handed_over_by: str

    @field_validator("*")
    @classmethod
    def not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Поле не может быть пустым")
        return value.strip()

    @field_validator("ttn_series")
    @classmethod
    def normalize_series(cls, value: str) -> str:
        return value.strip().upper()

    @property
    def series_and_number(self) -> str:
        return f"{self.ttn_series} {self.ttn_number}"

    @property
    def safe_identifier(self) -> str:
        return re.sub(r"[^0-9A-Za-zА-Яа-я_-]+", "_", self.series_and_number).strip("_")


FIELD_LABELS = {
    "vehicle": "Автомобиль",
    "driver": "Водитель",
    "series_and_number": "Серия и номер ТТН",
    "goods_accepted_by": "Товар к перевозке принял",
    "release_allowed_by": "Отпуск разрешил",
    "shipper_handed_over_by": "Сдал грузоотправитель",
}

INPUT_LABEL_TO_FIELD = {
    "автомобиль": "vehicle",
    "водитель": "driver",
    "серия и номер ттн": "series_and_number",
    "товар к перевозке принял": "goods_accepted_by",
    "отпуск разрешил": "release_allowed_by",
    "сдал грузоотправитель": "shipper_handed_over_by",
}


def empty_template_text() -> str:
    return "\n".join(
        [
            "Автомобиль: ",
            "Водитель: ",
            "Серия и номер ТТН: ",
            "Отпуск разрешил: ",
        ]
    )


def parse_series_and_number(value: str) -> tuple[str, str]:
    normalized = " ".join(value.strip().split())
    normalized = re.sub(r"^(?:TTN|ТТН)\s+", "", normalized, flags=re.IGNORECASE)
    match = re.match(r"^([A-Za-zА-Яа-яЁё]+)\s*[-/]?\s*(\d[\dA-Za-zА-Яа-яЁё/-]*)$", normalized)
    if not match:
        raise ValueError("Укажите серию и номер, например: ЕМ 1926709")
    return match.group(1).upper(), match.group(2)


def parse_edit_data_message(text: str) -> TtnEditData:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        raw_label, raw_value = line.split(":", 1)
        field_name = INPUT_LABEL_TO_FIELD.get(raw_label.strip().lower())
        if field_name:
            values[field_name] = raw_value.strip()

    required_fields = {
        "автомобиль": "vehicle",
        "водитель": "driver",
        "серия и номер ттн": "series_and_number",
        "отпуск разрешил": "release_allowed_by",
    }
    missing = [label for label, field in required_fields.items() if field not in values]
    if missing:
        raise ValueError("Не заполнены поля: " + ", ".join(missing))

    series, number = parse_series_and_number(values.pop("series_and_number"))
    values["goods_accepted_by"] = values.get("goods_accepted_by") or values["driver"]
    values["shipper_handed_over_by"] = (
        values.get("shipper_handed_over_by") or values["release_allowed_by"]
    )
    payload: dict[str, Any] = {
        **values,
        "ttn_series": series,
        "ttn_number": number,
    }
    try:
        return TtnEditData.model_validate(payload)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        raise ValueError(str(first_error.get("msg", "Проверьте заполненные данные"))) from exc
