import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.integrations.wildberries.exceptions import (
    WildberriesAuthError,
    WildberriesRateLimitError,
    WildberriesRequestError,
)
from app.integrations.wildberries.rate_limiter import AsyncRateLimiter
from app.integrations.wildberries.schemas import Feedback

logger = logging.getLogger(__name__)
_DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 30 * 60


class WildberriesClient:
    _rate_limit_cooldown_until = 0.0

    def __init__(
        self,
        base_url: str,
        api_token: str,
        *,
        max_retries: int = 5,
        connect_timeout: float = 10,
        read_timeout: float = 30,
        min_interval_seconds: float = 3.5,
        rate_limiter: AsyncRateLimiter | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._max_retries = max_retries
        self._rate_limiter = rate_limiter or AsyncRateLimiter(min_interval_seconds)
        timeout = httpx.Timeout(timeout=40, connect=connect_timeout, read=read_timeout, write=10)
        self._client = http_client or httpx.AsyncClient(base_url=self._base_url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def ping(self) -> bool:
        await self.get_unanswered_feedbacks(take=1, skip=0)
        return True

    async def get_unanswered_feedbacks(
        self,
        take: int,
        skip: int,
        order: str = "dateDesc",
    ) -> list[Feedback]:
        return await self._get_feedbacks(False, take, skip, order)

    async def get_answered_feedbacks(
        self,
        take: int,
        skip: int,
        order: str = "dateDesc",
    ) -> list[Feedback]:
        return await self._get_feedbacks(True, take, skip, order)

    async def _get_feedbacks(
        self,
        is_answered: bool,
        take: int,
        skip: int,
        order: str,
    ) -> list[Feedback]:
        response = await self._request(
            "GET",
            "/api/v1/feedbacks",
            params={
                "isAnswered": str(is_answered).lower(),
                "take": take,
                "skip": skip,
                "order": order,
            },
        )
        payload = response.json()
        raw_items = payload.get("data", {}).get("feedbacks", payload.get("feedbacks", []))
        return [Feedback.from_wb(item) for item in raw_items]

    async def send_feedback_answer(self, feedback_id: str, text: str) -> None:
        await self._request(
            "POST", "/api/v1/feedbacks/answer", json={"id": feedback_id, "text": text}
        )

    async def edit_feedback_answer(self, feedback_id: str, text: str) -> None:
        await self._request(
            "PATCH", "/api/v1/feedbacks/answer", json={"id": feedback_id, "text": text}
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        async def send() -> httpx.Response:
            return await self._client.request(
                method,
                path,
                headers={"Authorization": self._api_token},
                **kwargs,
            )

        return await self._retry(lambda: self._rate_limiter.run(send))

    async def _retry(self, send: Callable[[], Awaitable[httpx.Response]]) -> httpx.Response:
        self._raise_if_rate_limited()
        retry_statuses = {429, 500, 502, 503, 504}
        last_status = 0
        for attempt in range(self._max_retries + 1):
            try:
                response = await send()
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise WildberriesRequestError(0, "Wildberries network error") from exc
                await asyncio.sleep(self._backoff_delay(attempt, None))
                continue

            if response.status_code < 400:
                return response
            last_status = response.status_code
            if response.status_code in {401, 403}:
                raise WildberriesAuthError("Wildberries rejected API token")
            if response.status_code not in retry_statuses:
                raise WildberriesRequestError(response.status_code, "Wildberries request failed")
            retry_after = self._retry_after_seconds(
                response.headers.get("X-Ratelimit-Retry")
                or response.headers.get("X-RateLimit-Retry")
                or response.headers.get("Retry-After")
            )
            logger.warning(
                "wb retryable error",
                extra={
                    "service": "wildberries",
                    "event": "wb_rate_limit" if response.status_code == 429 else "wb_retry",
                    "retry_after_seconds": retry_after,
                },
            )
            if response.status_code == 429:
                self._set_rate_limit_cooldown(retry_after)
                raise WildberriesRateLimitError(
                    "Wildberries rate limit reached",
                    retry_after_seconds=self._rate_limit_remaining_seconds(),
                )
            if attempt >= self._max_retries:
                raise WildberriesRequestError(response.status_code, "Wildberries retries exhausted")
            await asyncio.sleep(self._backoff_delay(attempt, retry_after))
        raise WildberriesRequestError(last_status, "Wildberries retries exhausted")

    @staticmethod
    def _backoff_delay(attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return retry_after
        return min(max(2.0**attempt, 60.0), 180.0)

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float | None:
        if not value:
            return None
        if value.isdigit():
            return float(value)
        try:
            return max(parsedate_to_datetime(value).timestamp() - time.time(), 0.0)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _raise_if_rate_limited(cls) -> None:
        remaining = cls._rate_limit_remaining_seconds()
        if remaining > 0:
            raise WildberriesRateLimitError(
                "Wildberries category cooldown is active",
                retry_after_seconds=remaining,
            )

    @classmethod
    def _set_rate_limit_cooldown(cls, retry_after: float | None) -> None:
        delay = retry_after or _DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS
        cls._rate_limit_cooldown_until = max(
            cls._rate_limit_cooldown_until, time.time() + delay
        )

    @classmethod
    def _rate_limit_remaining_seconds(cls) -> float:
        return max(cls._rate_limit_cooldown_until - time.time(), 0.0)
