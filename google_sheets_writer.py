import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from models import ApiTokens, ExportData, NomenclatureRow, PriceTemplateRow, WildberriesExportError

logger = logging.getLogger(__name__)

API_SHEET_NAME = "API ключ"
EXPORT_SHEET_NAME = "Выгрузки"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
TOKEN_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"  # noqa: S105

NOMENCLATURE_HEADERS = ["Артикул продавца", "Артикул WB", "Наименование"]
PRICE_HEADERS = [
    "Артикул продавца",
    "Артикул WB",
    "Размер",
    "ID размера",
    "Текущая цена",
    "Новая цена",
    "Текущая скидка, %",
    "Новая скидка, %",
    "Цена со скидкой",
    "Цена WB Клуб",
    "Скидка WB Клуб, %",
    "Валюта",
    "Цена по размерам",
    "Низкая оборачиваемость",
]


@dataclass(frozen=True, slots=True)
class SheetMetadata:
    spreadsheet_id: str
    spreadsheet_url: str
    title: str
    sheets: dict[str, int]


class GoogleSheetsExportStore:
    def __init__(
        self,
        spreadsheet: str,
        *,
        credentials: "ServiceAccountCredentials | None" = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.spreadsheet_id = parse_spreadsheet_id(spreadsheet)
        self._credentials = credentials or ServiceAccountCredentials.from_env()
        self._client = http_client or httpx.Client(timeout=httpx.Timeout(40.0, connect=10.0))

    def close(self) -> None:
        self._client.close()

    def validate_and_read_tokens(self) -> ApiTokens:
        metadata = self.get_metadata()
        if API_SHEET_NAME not in metadata.sheets:
            raise WildberriesExportError(f'В таблице нет листа "{API_SHEET_NAME}"')
        rows = self._values_get(f"'{API_SHEET_NAME}'!A1:B200").get("values", [])
        if not isinstance(rows, list):
            raise WildberriesExportError(f'Не удалось прочитать лист "{API_SHEET_NAME}"')
        content_token = _find_token(rows, "Контент", fallback_row=0)
        prices_token = _find_token(rows, "Цены и скидки", fallback_row=2)
        if not content_token:
            raise WildberriesExportError('Не найден токен категории "Контент"')
        if not prices_token:
            raise WildberriesExportError('Не найден токен категории "Цены и скидки"')
        return ApiTokens(content=content_token, prices=prices_token)

    def get_metadata(self) -> SheetMetadata:
        payload = self._request(
            "GET",
            f"https://sheets.googleapis.com/v4/spreadsheets/{self.spreadsheet_id}",
            params={
                "fields": (
                    "spreadsheetUrl,properties.title,"
                    "sheets.properties(sheetId,title,gridProperties)"
                )
            },
        )
        sheets: dict[str, int] = {}
        for sheet in payload.get("sheets", []):
            properties = sheet.get("properties", {})
            title = properties.get("title")
            sheet_id = properties.get("sheetId")
            if isinstance(title, str) and isinstance(sheet_id, int):
                sheets[title] = sheet_id
        title = payload.get("properties", {}).get("title", "")
        spreadsheet_url = payload.get("spreadsheetUrl", "")
        return SheetMetadata(
            spreadsheet_id=self.spreadsheet_id,
            spreadsheet_url=str(spreadsheet_url),
            title=str(title),
            sheets=sheets,
        )

    def create_backup(self) -> str:
        metadata = self.get_metadata()
        backup_name = (
            f"{metadata.title or self.spreadsheet_id} backup {datetime.now():%Y%m%d_%H%M%S}"
        )
        payload = self._request(
            "POST",
            f"https://www.googleapis.com/drive/v3/files/{self.spreadsheet_id}/copy",
            params={"fields": "id,webViewLink"},
            json={"name": backup_name},
        )
        backup_url = str(payload.get("webViewLink") or "")
        logger.info("wb_export_backup", extra={"backup_url": backup_url})
        return backup_url

    def update_export_sheet(self, data: ExportData) -> str:
        metadata = self.get_metadata()
        sheet_id = metadata.sheets.get(EXPORT_SHEET_NAME)
        if sheet_id is None:
            sheet_id = self._add_export_sheet()

        values = _build_values(data)
        self._values_clear(f"'{EXPORT_SHEET_NAME}'!A:R")
        self._values_update(f"'{EXPORT_SHEET_NAME}'!A1:R{len(values)}", values)
        self._format_export_sheet(sheet_id, max(len(values), 7), len(data.prices))
        return metadata.spreadsheet_url

    def _add_export_sheet(self) -> int:
        payload = self._batch_update(
            [
                {
                    "addSheet": {
                        "properties": {
                            "title": EXPORT_SHEET_NAME,
                            "gridProperties": {"rowCount": 1000, "columnCount": 18},
                        }
                    }
                }
            ]
        )
        replies = payload.get("replies", [])
        sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
        if not isinstance(sheet_id, int):
            raise WildberriesExportError(f'Не удалось создать лист "{EXPORT_SHEET_NAME}"')
        return sheet_id

    def _format_export_sheet(self, sheet_id: int, last_row: int, price_rows: int) -> None:
        requests: list[dict[str, Any]] = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 6,
                        "endRowIndex": 7,
                        "startColumnIndex": 0,
                        "endColumnIndex": 18,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.12, "green": 0.16, "blue": 0.22},
                            "textFormat": {
                                "bold": True,
                                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                            },
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {
                            "frozenRowCount": 7,
                            "rowCount": max(last_row, 1000),
                            "columnCount": 18,
                        },
                    },
                    "fields": "gridProperties(frozenRowCount,rowCount,columnCount)",
                }
            },
            {
                "setBasicFilter": {
                    "filter": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 6,
                            "endRowIndex": max(last_row, 7),
                            "startColumnIndex": 0,
                            "endColumnIndex": 18,
                        }
                    }
                }
            },
            _number_format(sheet_id, 1, 2, "0", last_row),
            _number_format(sheet_id, 5, 6, "0", last_row),
            _number_format(sheet_id, 7, 8, "0", last_row),
            _number_format(sheet_id, 8, 9, "#,##0.00", last_row),
            _number_format(sheet_id, 12, 14, "#,##0.00", last_row),
            _number_format(sheet_id, 10, 11, "0", last_row),
            _number_format(sheet_id, 14, 15, "0", last_row),
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": 18,
                    }
                }
            },
        ]
        if price_rows:
            for start_col in (9, 11):
                requests.append(
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 7,
                                "endRowIndex": 7 + price_rows,
                                "startColumnIndex": start_col,
                                "endColumnIndex": start_col + 1,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "backgroundColor": {"red": 1, "green": 0.95, "blue": 0.8},
                                    "textFormat": {
                                        "foregroundColor": {
                                            "red": 0.12,
                                            "green": 0.31,
                                            "blue": 0.47,
                                        }
                                    },
                                }
                            },
                            "fields": "userEnteredFormat(backgroundColor,textFormat)",
                        }
                    }
                )
        self._batch_update(requests)

    def _values_get(self, range_name: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"https://sheets.googleapis.com/v4/spreadsheets/{self.spreadsheet_id}/values/{range_name}",
        )

    def _values_clear(self, range_name: str) -> None:
        self._request(
            "POST",
            (
                f"https://sheets.googleapis.com/v4/spreadsheets/{self.spreadsheet_id}"
                f"/values/{range_name}:clear"
            ),
            json={},
        )

    def _values_update(self, range_name: str, values: list[list[Any]]) -> None:
        self._request(
            "PUT",
            f"https://sheets.googleapis.com/v4/spreadsheets/{self.spreadsheet_id}/values/{range_name}",
            params={"valueInputOption": "USER_ENTERED"},
            json={"range": range_name, "majorDimension": "ROWS", "values": values},
        )

    def _batch_update(self, requests: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"https://sheets.googleapis.com/v4/spreadsheets/{self.spreadsheet_id}:batchUpdate",
            json={"requests": requests},
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self._credentials.access_token(self._client)}"
        response = self._client.request(method, url, headers=headers, **kwargs)
        if response.status_code == 401:
            raise WildberriesExportError("Google API отклонил учетные данные service account")
        if response.status_code == 403:
            message = _google_error_message(response)
            if "has not been used" in message or "disabled" in message:
                raise WildberriesExportError(
                    "В проекте service account не включен нужный Google API: "
                    f"{message}"
                )
            raise WildberriesExportError(
                "Нет доступа к Google таблице. Расшарьте ее на email service account."
            )
        if response.status_code >= 400:
            message = _google_error_message(response)
            suffix = f": {message}" if message else ""
            raise WildberriesExportError(f"Google API вернул ошибку {response.status_code}{suffix}")
        if not response.content:
            return {}
        payload = response.json()
        if not isinstance(payload, dict):
            raise WildberriesExportError("Google API вернул неожиданный ответ")
        return payload


class ServiceAccountCredentials:
    def __init__(self, info: dict[str, Any], scopes: list[str]) -> None:
        self._client_email = str(info.get("client_email") or "")
        self._private_key = str(info.get("private_key") or "")
        self._token_uri = str(info.get("token_uri") or "https://oauth2.googleapis.com/token")
        self._scopes = scopes
        self._token: str | None = None
        self._expires_at = 0.0
        if not self._client_email or not self._private_key:
            raise WildberriesExportError("Некорректный JSON service account")

    @classmethod
    def from_env(cls) -> "ServiceAccountCredentials":
        raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        file_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        if raw_json:
            info = json.loads(raw_json)
        elif file_path:
            info = json.loads(Path(file_path).read_text(encoding="utf-8"))
        else:
            raise WildberriesExportError(
                "Укажите GOOGLE_SERVICE_ACCOUNT_FILE или GOOGLE_SERVICE_ACCOUNT_JSON"
            )
        if not isinstance(info, dict):
            raise WildberriesExportError("Некорректный JSON service account")
        return cls(info, [SHEETS_SCOPE, DRIVE_SCOPE])

    @property
    def client_email(self) -> str:
        return self._client_email

    def access_token(self, client: httpx.Client) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        assertion = self._jwt_assertion()
        response = client.post(
            self._token_uri,
            data={"grant_type": TOKEN_GRANT_TYPE, "assertion": assertion},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            raise WildberriesExportError("Не удалось получить Google OAuth токен")
        payload = response.json()
        token = payload.get("access_token")
        expires_in = payload.get("expires_in", 3600)
        if not isinstance(token, str):
            raise WildberriesExportError("Google OAuth не вернул access token")
        self._token = token
        self._expires_at = time.time() + int(expires_in)
        return token

    def _jwt_assertion(self) -> str:
        now = datetime.now(UTC)
        header = {"alg": "RS256", "typ": "JWT"}
        claims = {
            "iss": self._client_email,
            "scope": " ".join(self._scopes),
            "aud": self._token_uri,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        }
        signing_input = f"{_b64_json(header)}.{_b64_json(claims)}".encode()
        private_key = serialization.load_pem_private_key(self._private_key.encode(), password=None)
        signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        return f"{signing_input.decode()}.{_b64(signature)}"


def parse_spreadsheet_id(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme:
        return value.strip()
    parts = [part for part in parsed.path.split("/") if part]
    if "d" in parts:
        index = parts.index("d")
        if index + 1 < len(parts):
            return parts[index + 1]
    raise WildberriesExportError("Не удалось определить spreadsheet id из ссылки Google Sheets")


def _find_token(rows: list[Any], label: str, *, fallback_row: int) -> str:
    label_lower = label.lower()
    for row in rows:
        if isinstance(row, list) and row and label_lower in str(row[0]).lower():
            return str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
    if len(rows) > fallback_row and isinstance(rows[fallback_row], list):
        row = rows[fallback_row]
        if len(row) > 1 and row[1] is not None:
            return str(row[1]).strip()
    return ""


def _build_values(data: ExportData) -> list[list[Any]]:
    last_row = max(7 + len(data.nomenclatures), 7 + len(data.prices), 7)
    values = [["" for _ in range(18)] for _ in range(last_row)]
    values[0][0] = "Выгрузка Wildberries"
    values[1][0] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    values[2][0] = "Успешно"
    values[3][0] = len(data.nomenclatures)
    values[4][0] = len(data.prices)
    values[6][0:3] = NOMENCLATURE_HEADERS
    values[6][4:18] = PRICE_HEADERS
    for index, row in enumerate(data.nomenclatures, start=7):
        values[index][0:3] = _nomenclature_values(row)
    for index, row in enumerate(data.prices, start=7):
        values[index][4:18] = _price_values(row)
    return values


def _nomenclature_values(row: NomenclatureRow) -> list[Any]:
    return [row.vendor_code, row.nm_id, row.title]


def _price_values(row: PriceTemplateRow) -> list[Any]:
    return [
        row.vendor_code,
        row.nm_id,
        row.tech_size_name,
        row.size_id,
        row.current_price,
        "",
        row.current_discount,
        "",
        row.discounted_price,
        row.club_discounted_price,
        row.club_discount,
        row.currency,
        row.editable_size_price,
        row.is_bad_turnover,
    ]


def _number_format(
    sheet_id: int,
    start_col: int,
    end_col: int,
    pattern: str,
    last_row: int,
) -> dict[str, Any]:
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 7,
                "endRowIndex": last_row,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "cell": {
                "userEnteredFormat": {
                    "numberFormat": {"type": "NUMBER", "pattern": pattern}
                }
            },
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _b64_json(value: dict[str, Any]) -> str:
    return _b64(json.dumps(value, separators=(",", ":")).encode())


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _google_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if not isinstance(error, dict):
        return ""
    message = error.get("message")
    return str(message) if message else ""
