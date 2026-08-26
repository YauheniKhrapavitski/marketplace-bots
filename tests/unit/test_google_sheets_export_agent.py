import json
from collections.abc import Callable

import httpx
import pytest

from google_sheets_writer import GoogleSheetsExportStore, parse_spreadsheet_id
from models import ExportData, NomenclatureRow, PriceTemplateRow, WildberriesExportError


def test_parse_spreadsheet_id_from_url_and_plain_id() -> None:
    url = "https://docs.google.com/spreadsheets/d/sheet123/edit?gid=915146405#gid=915146405"

    assert parse_spreadsheet_id(url) == "sheet123"
    assert parse_spreadsheet_id("sheet123") == "sheet123"


def test_reads_both_tokens_from_google_sheet_labels() -> None:
    store = _store(
        [
            _metadata(["API ключ", "Выгрузки"]),
            {
                "range": "'API ключ'!A1:B200",
                "values": [
                    ["Ключ Контент", "content"],
                    [],
                    ["Ключ Цены и скидки", "prices"],
                ],
            },
        ]
    )

    try:
        tokens = store.validate_and_read_tokens()
    finally:
        store.close()

    assert tokens.content == "content"
    assert tokens.prices == "prices"


def test_reads_tokens_from_fallback_cells() -> None:
    store = _store(
        [
            _metadata(["API ключ"]),
            {"values": [["", "content"], [], ["", "prices"]]},
        ]
    )

    try:
        tokens = store.validate_and_read_tokens()
    finally:
        store.close()

    assert tokens.content == "content"
    assert tokens.prices == "prices"


def test_missing_api_key_sheet_fails() -> None:
    store = _store([_metadata(["Выгрузки"])])

    with pytest.raises(WildberriesExportError):
        store.validate_and_read_tokens()
    store.close()


def test_update_export_sheet_writes_values_and_formats() -> None:
    requests: list[httpx.Request] = []
    store = _store(
        [
            _metadata(["API ключ", "Выгрузки"], export_sheet_id=777),
            {},
            {"updatedCells": 36},
            {"replies": []},
        ],
        requests=requests,
    )
    data = ExportData(
        nomenclatures=[NomenclatureRow(vendor_code="АРТ", nm_id=123, title="Название")],
        prices=[
            PriceTemplateRow(
                vendor_code="АРТ",
                nm_id=123,
                tech_size_name="42",
                size_id=55,
                current_price=1000,
                current_discount=10,
                discounted_price=900,
                club_discounted_price=870,
                club_discount=3,
                currency="RUB",
                editable_size_price=True,
                is_bad_turnover=False,
            )
        ],
    )

    try:
        url = store.update_export_sheet(data)
    finally:
        store.close()

    assert url == "https://docs.google.com/spreadsheets/d/sheet123/edit"
    value_update = [request for request in requests if request.method == "PUT"][0]
    payload = value_update.read().decode()
    assert "АРТ" in payload
    assert "Название" in payload
    assert "content" not in payload
    assert "prices" not in payload

    batch = [request for request in requests if request.url.path.endswith(":batchUpdate")][0]
    batch_payload = json.loads(batch.read().decode())
    input_ranges = [
        request["repeatCell"]["range"]
        for request in batch_payload["requests"]
        if "repeatCell" in request
        and request["repeatCell"]["range"].get("startRowIndex") == 7
        and request["repeatCell"]["range"].get("startColumnIndex") in {9, 11}
    ]
    assert [item["startColumnIndex"] for item in input_ranges] == [9, 11]


def test_update_creates_export_sheet_when_missing() -> None:
    requests: list[httpx.Request] = []
    store = _store(
        [
            _metadata(["API ключ"]),
            {"replies": [{"addSheet": {"properties": {"sheetId": 888}}}]},
            {},
            {"updatedCells": 126},
            {"replies": []},
        ],
        requests=requests,
    )

    try:
        store.update_export_sheet(ExportData(nomenclatures=[], prices=[]))
    finally:
        store.close()

    add_sheet_batches = [
        request for request in requests if request.url.path.endswith(":batchUpdate")
    ]
    add_sheet_payload = json.loads(add_sheet_batches[0].read().decode())
    assert "addSheet" in add_sheet_payload["requests"][0]


def test_create_backup_uses_drive_copy() -> None:
    requests: list[httpx.Request] = []
    store = _store(
        [
            _metadata(["API ключ", "Выгрузки"]),
            {"id": "backup123", "webViewLink": "https://docs.google.com/spreadsheets/d/backup123/edit"},
        ],
        requests=requests,
    )

    try:
        backup_url = store.create_backup()
    finally:
        store.close()

    assert backup_url.endswith("/backup123/edit")
    assert any("/drive/v3/files/sheet123/copy" in str(request.url) for request in requests)


def test_google_errors_do_not_include_tokens() -> None:
    store = _store([httpx.Response(403, json={"error": {"message": "denied"}})])

    with pytest.raises(WildberriesExportError) as exc_info:
        store.get_metadata()
    store.close()

    assert "access-token" not in str(exc_info.value)


class FakeCredentials:
    def access_token(self, _: httpx.Client) -> str:
        return "access-token"


def _store(
    responses: list[dict[str, object] | httpx.Response],
    *,
    requests: list[httpx.Request] | None = None,
) -> GoogleSheetsExportStore:
    captured = requests if requests is not None else []
    transport = httpx.MockTransport(_sequence_handler(responses, captured))
    return GoogleSheetsExportStore(
        "https://docs.google.com/spreadsheets/d/sheet123/edit",
        credentials=FakeCredentials(),  # type: ignore[arg-type]
        http_client=httpx.Client(transport=transport),
    )


def _sequence_handler(
    responses: list[dict[str, object] | httpx.Response],
    requests: list[httpx.Request],
) -> Callable[[httpx.Request], httpx.Response]:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        index = calls["count"]
        calls["count"] += 1
        if index >= len(responses):
            return httpx.Response(200, json={})
        response = responses[index]
        if isinstance(response, httpx.Response):
            return response
        return httpx.Response(200, json=response)

    return handler


def _metadata(sheet_names: list[str], *, export_sheet_id: int = 222) -> dict[str, object]:
    sheets = []
    for index, name in enumerate(sheet_names):
        sheet_id = export_sheet_id if name == "Выгрузки" else index + 1
        sheets.append({"properties": {"sheetId": sheet_id, "title": name}})
    return {
        "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/sheet123/edit",
        "properties": {"title": "WB Export"},
        "sheets": sheets,
    }
