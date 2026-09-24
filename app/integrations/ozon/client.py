import asyncio
import logging
from collections.abc import Awaitable, Callable
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.integrations.ozon.exceptions import (
    OzonAuthError,
    OzonRateLimitError,
    OzonRequestError,
)
from app.integrations.ozon.schemas import OzonReview
from app.integrations.wildberries.rate_limiter import AsyncRateLimiter

logger = logging.getLogger(__name__)


class OzonClient:
    def __init__(
        self,
        base_url: str,
        client_id: str,
        api_key: str,
        *,
        max_retries: int = 5,
        connect_timeout: float = 10,
        read_timeout: float = 30,
        rate_limiter: AsyncRateLimiter | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._api_key = api_key
        self._max_retries = max_retries
        self._rate_limiter = rate_limiter or AsyncRateLimiter(0.25)
        timeout = httpx.Timeout(timeout=40, connect=connect_timeout, read=read_timeout, write=10)
        self._client = http_client or httpx.AsyncClient(base_url=self._base_url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def ping(self) -> bool:
        await self.count_reviews()
        return True

    async def count_reviews(self) -> dict[str, Any]:
        response = await self._request("POST", "/v1/review/count", json={})
        payload = response.json()
        return dict(payload.get("result") or payload)

    async def list_reviews(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        sort_dir: str = "DESC",
    ) -> list[OzonReview]:
        if offset:
            return []
        body: dict[str, object] = {"last_id": "", "limit": limit, "sort_dir": sort_dir}
        if status:
            body["filters"] = {"status": status}
        response = await self._request("POST", "/v2/review/list", json=body)
        payload = response.json()
        result = payload.get("result") or payload
        raw_items = result.get("reviews") or result.get("items") or []
        reviews: list[OzonReview] = []
        for item in raw_items:
            review_id = item.get("id") or item.get("review_id") or item.get("reviewId")
            if review_id and self._needs_info(item):
                try:
                    info = await self.get_review_info(str(review_id))
                except OzonRequestError:
                    info = item
                else:
                    item = {**item, **info}
            reviews.append(OzonReview.from_ozon(item))
        return reviews

    async def get_roles(self) -> dict[str, Any]:
        response = await self._request("POST", "/v1/roles", json={})
        payload = response.json()
        return dict(payload.get("result") or payload)

    async def get_review_info(self, review_id: str) -> dict[str, Any]:
        response = await self._request("POST", "/v1/review/info", json={"review_id": review_id})
        payload = response.json()
        return dict(payload.get("result") or payload)

    async def list_review_comments(self, review_id: str) -> list[dict[str, Any]]:
        response = await self._request(
            "POST", "/v1/review/comment/list", json={"review_id": review_id}
        )
        payload = response.json()
        result = payload.get("result") or payload
        comments = result.get("comments") or result.get("items") or []
        return [dict(item) for item in comments]

    async def send_review_answer(self, review_id: str, text: str) -> None:
        await self._request(
            "POST",
            "/v1/review/comment/create",
            json={"review_id": review_id, "text": text},
        )

    async def mark_reviews_processed(self, review_ids: list[str]) -> None:
        if not review_ids:
            return
        await self._request(
            "POST",
            "/v1/review/change-status",
            json={"review_ids": review_ids, "status": "PROCESSED"},
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        async def send() -> httpx.Response:
            return await self._client.request(
                method,
                path,
                headers={
                    "Client-Id": self._client_id,
                    "Api-Key": self._api_key,
                    "Content-Type": "application/json",
                },
                **kwargs,
            )

        return await self._retry(lambda: self._rate_limiter.run(send))

    async def _retry(self, send: Callable[[], Awaitable[httpx.Response]]) -> httpx.Response:
        retry_statuses = {429, 500, 502, 503, 504}
        last_status = 0
        for attempt in range(self._max_retries + 1):
            try:
                response = await send()
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise OzonRequestError(
                        0,
                        "Ozon network error",
                        self._exception_detail(exc),
                    ) from exc
                await asyncio.sleep(self._backoff_delay(attempt, None))
                continue
            if response.status_code < 400:
                return response
            last_status = response.status_code
            if response.status_code in {401, 403}:
                raise OzonAuthError(
                    "Ozon rejected API credentials",
                    response.status_code,
                    self._response_detail(response),
                )
            if response.status_code not in retry_statuses:
                raise OzonRequestError(
                    response.status_code,
                    "Ozon request failed",
                    self._response_detail(response),
                )
            retry_after = self._retry_after_seconds(response.headers.get("Retry-After"))
            logger.warning(
                "ozon retryable error",
                extra={"service": "ozon", "event": "ozon_retry"},
            )
            if attempt >= self._max_retries:
                if response.status_code == 429:
                    raise OzonRateLimitError("Ozon rate limit retries exhausted")
                raise OzonRequestError(
                    response.status_code,
                    "Ozon retries exhausted",
                    self._response_detail(response),
                )
            await asyncio.sleep(self._backoff_delay(attempt, retry_after))
        raise OzonRequestError(last_status, "Ozon retries exhausted")

    @staticmethod
    def _needs_info(item: dict[str, Any]) -> bool:
        return not any(item.get(key) for key in ("text", "review_text", "reviewText"))

    @staticmethod
    def _backoff_delay(attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return retry_after
        return min(2.0**attempt, 30.0)

    @staticmethod
    def _response_detail(response: httpx.Response) -> str:
        text = response.text.replace("\n", " ").strip()
        return text[:300]

    @staticmethod
    def _exception_detail(exc: Exception) -> str:
        text = str(exc).replace("\n", " ").strip()
        detail = f"{type(exc).__name__}: {text}" if text else type(exc).__name__
        return detail[:300]

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float | None:
        if not value:
            return None
        if value.isdigit():
            return float(value)
        try:
            return max((parsedate_to_datetime(value).timestamp()), 0.0)
        except (TypeError, ValueError):
            return None
