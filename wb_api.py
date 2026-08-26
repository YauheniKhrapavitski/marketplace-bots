import logging
import time
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from models import JsonObject, NomenclatureRow, PriceTemplateRow, WildberriesApiError

logger = logging.getLogger(__name__)

CONTENT_BASE_URL = "https://content-api.wildberries.ru"
PRICES_BASE_URL = "https://discounts-prices-api.wildberries.ru"
CONTENT_LIMIT = 100
PRICES_LIMIT = 1000
MAX_PAGES = 10_000


class WildberriesExportClient:
    def __init__(
        self,
        *,
        content_token: str,
        prices_token: str,
        content_base_url: str = CONTENT_BASE_URL,
        prices_base_url: str = PRICES_BASE_URL,
        timeout: float = 40.0,
        max_retries: int = 5,
        sleep: Callable[[float], None] = time.sleep,
        content_http_client: httpx.Client | None = None,
        prices_http_client: httpx.Client | None = None,
    ) -> None:
        self._content_token = content_token
        self._prices_token = prices_token
        self._max_retries = max_retries
        self._sleep = sleep
        timeout_config = httpx.Timeout(timeout=timeout, connect=10.0, read=timeout, write=10.0)
        self._content_client = content_http_client or httpx.Client(
            base_url=content_base_url, timeout=timeout_config
        )
        self._prices_client = prices_http_client or httpx.Client(
            base_url=prices_base_url, timeout=timeout_config
        )

    def close(self) -> None:
        self._content_client.close()
        self._prices_client.close()

    def fetch_nomenclatures(self) -> list[NomenclatureRow]:
        report_name = "Перечень номенклатур"
        seen_nm_ids: set[int] = set()
        rows: list[NomenclatureRow] = []
        cursor: JsonObject = {"limit": CONTENT_LIMIT}
        previous_position: tuple[Any, Any] | None = None

        for page in range(1, MAX_PAGES + 1):
            payload = {
                "settings": {
                    "sort": {"ascending": True},
                    "filter": {"withPhoto": -1},
                    "cursor": cursor,
                }
            }
            response = self._request(
                self._content_client,
                "POST",
                "/content/v2/get/cards/list",
                report_name=report_name,
                headers={
                    "Authorization": self._content_token,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            data = self._json_object(response, report_name)
            cards = data.get("cards")
            cursor_data = data.get("cursor")
            if not isinstance(cards, list) or not isinstance(cursor_data, dict):
                raise WildberriesApiError(
                    report_name,
                    response.status_code,
                    "неожиданная структура ответа",
                )

            logger.info(
                "wb_export_page",
                extra={
                    "report": "nomenclatures",
                    "page": page,
                    "records": len(cards),
                    "retries": 0,
                },
            )
            if not cards:
                break

            for card in cards:
                if not isinstance(card, dict):
                    continue
                nm_id = _to_int(card.get("nmID"))
                if nm_id is None or nm_id in seen_nm_ids:
                    continue
                seen_nm_ids.add(nm_id)
                rows.append(
                    NomenclatureRow(
                        vendor_code=_to_text(card.get("vendorCode")),
                        nm_id=nm_id,
                        title=_to_text(card.get("title")),
                    )
                )

            total = _to_int(cursor_data.get("total"))
            updated_at = cursor_data.get("updatedAt")
            nm_id = cursor_data.get("nmID")
            next_position = (updated_at, nm_id)
            if total is not None and total < CONTENT_LIMIT:
                break
            if next_position == previous_position:
                break
            previous_position = next_position
            if updated_at is None or nm_id is None:
                break
            cursor = {"limit": CONTENT_LIMIT, "updatedAt": updated_at, "nmID": nm_id}
        else:
            raise WildberriesApiError(report_name, 0, "остановлена защита от бесконечной пагинации")

        rows.sort(key=lambda row: row.nm_id)
        logger.info("wb_export_done", extra={"report": "nomenclatures", "records": len(rows)})
        return rows

    def fetch_price_template(self) -> list[PriceTemplateRow]:
        report_name = "Шаблон обновления цен и скидок"
        seen: set[tuple[int, int | None]] = set()
        rows: list[PriceTemplateRow] = []
        offset = 0

        for page in range(1, MAX_PAGES + 1):
            response = self._request(
                self._prices_client,
                "GET",
                "/api/v2/list/goods/filter",
                report_name=report_name,
                headers={"Authorization": self._prices_token},
                params={"limit": PRICES_LIMIT, "offset": offset},
            )
            payload = self._json_object(response, report_name)
            data = payload.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("listGoods"), list):
                raise WildberriesApiError(
                    report_name,
                    response.status_code,
                    "неожиданная структура ответа",
                )
            goods = data["listGoods"]
            logger.info(
                "wb_export_page",
                extra={"report": "prices", "page": page, "records": len(goods), "retries": 0},
            )
            if not goods:
                break

            for item in goods:
                if not isinstance(item, dict):
                    continue
                nm_id = _to_int(item.get("nmID"))
                if nm_id is None:
                    continue
                sizes = item.get("sizes")
                if isinstance(sizes, list) and sizes:
                    for size in sizes:
                        if isinstance(size, dict):
                            row = self._price_row(item, size, nm_id)
                            key = (row.nm_id, row.size_id)
                            if key not in seen:
                                seen.add(key)
                                rows.append(row)
                else:
                    row = self._price_row(item, {}, nm_id)
                    key = (row.nm_id, row.size_id)
                    if key not in seen:
                        seen.add(key)
                        rows.append(row)
            offset += PRICES_LIMIT
        else:
            raise WildberriesApiError(report_name, 0, "остановлена защита от бесконечной пагинации")

        rows.sort(key=lambda row: (row.nm_id, row.size_id if row.size_id is not None else -1))
        logger.info("wb_export_done", extra={"report": "prices", "records": len(rows)})
        return rows

    def _price_row(self, item: JsonObject, size: JsonObject, nm_id: int) -> PriceTemplateRow:
        return PriceTemplateRow(
            vendor_code=_to_text(item.get("vendorCode")),
            nm_id=nm_id,
            tech_size_name=_to_text(size.get("techSizeName")),
            size_id=_to_int(size.get("sizeID")),
            current_price=_to_number(size.get("price")),
            current_discount=_to_number(item.get("discount")),
            discounted_price=_to_number(size.get("discountedPrice")),
            club_discounted_price=_to_number(size.get("clubDiscountedPrice")),
            club_discount=_to_number(item.get("clubDiscount")),
            currency=_to_text(item.get("currencyIsoCode4217")),
            editable_size_price=_to_bool(item.get("editableSizePrice")),
            is_bad_turnover=_to_bool(item.get("isBadTurnover")),
        )

    def _request(
        self,
        client: httpx.Client,
        method: str,
        path: str,
        *,
        report_name: str,
        **kwargs: Any,
    ) -> httpx.Response:
        retryable = {429, 500, 502, 503, 504}
        last_status = 0
        for attempt in range(self._max_retries + 1):
            try:
                response = client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise WildberriesApiError(report_name, 0, "сетевая ошибка Wildberries") from exc
                self._log_retry(report_name, attempt + 1, 0)
                self._sleep(self._backoff_delay(attempt, None))
                continue

            if response.status_code < 400:
                return response

            last_status = response.status_code
            if response.status_code == 400:
                raise WildberriesApiError(report_name, 400, "неправильные параметры запроса")
            if response.status_code == 401:
                raise WildberriesApiError(report_name, 401, "неверный или просроченный токен")
            if response.status_code == 403:
                raise WildberriesApiError(report_name, 403, "у токена нет нужной категории доступа")
            if response.status_code not in retryable:
                raise WildberriesApiError(
                    report_name,
                    response.status_code,
                    "запрос Wildberries не выполнен",
                )
            if attempt >= self._max_retries:
                raise WildberriesApiError(report_name, last_status, "исчерпаны повторные попытки")
            retry_after = self._retry_after_seconds(response.headers.get("Retry-After"))
            self._log_retry(report_name, attempt + 1, response.status_code)
            self._sleep(self._backoff_delay(attempt, retry_after))
        raise WildberriesApiError(report_name, last_status, "исчерпаны повторные попытки")

    @staticmethod
    def _json_object(response: httpx.Response, report_name: str) -> JsonObject:
        try:
            payload = response.json()
        except ValueError as exc:
            raise WildberriesApiError(
                report_name,
                response.status_code,
                "ответ не является JSON",
            ) from exc
        if not isinstance(payload, dict):
            raise WildberriesApiError(
                report_name,
                response.status_code,
                "неожиданная структура ответа",
            )
        if payload.get("error") is True:
            raise WildberriesApiError(
                report_name,
                response.status_code,
                "Wildberries вернул ошибку",
            )
        return payload

    @staticmethod
    def _backoff_delay(attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return retry_after
        return min(2.0**attempt, 30.0)

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            pass
        try:
            retry_at = parsedate_to_datetime(value).timestamp()
        except (TypeError, ValueError):
            return None
        return max(retry_at - time.time(), 0.0)

    @staticmethod
    def _log_retry(report_name: str, retry_number: int, status_code: int) -> None:
        logger.warning(
            "wb_export_retry",
            extra={"report": report_name, "retry": retry_number, "status_code": status_code},
        )


def _to_text(value: Any) -> str:
    return "" if value is None else str(value)


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_number(value: Any) -> float | int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "да"}:
            return True
        if lowered in {"false", "0", "no", "нет"}:
            return False
    return None
