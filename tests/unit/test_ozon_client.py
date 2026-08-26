import httpx
import pytest

from app.integrations.ozon.client import OzonClient
from app.integrations.ozon.exceptions import OzonRequestError
from app.integrations.wildberries.rate_limiter import AsyncRateLimiter


@pytest.mark.asyncio
async def test_mark_reviews_processed_uses_change_status_payload() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"result": True})

    client = OzonClient(
        "https://example.test",
        "client-id",
        "api-key",
        max_retries=0,
        rate_limiter=AsyncRateLimiter(0),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        ),
    )
    try:
        await client.mark_reviews_processed(["review-1", "review-2"])
    finally:
        await client.aclose()

    assert requests[0].method == "POST"
    assert requests[0].url.path == "/v1/review/change-status"
    assert requests[0].read().decode() == (
        '{"review_ids":["review-1","review-2"],"status":"PROCESSED"}'
    )


@pytest.mark.asyncio
async def test_send_review_answer_preserves_ozon_error_detail() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": 3, "message": "review is not commentable"})

    client = OzonClient(
        "https://example.test",
        "client-id",
        "api-key",
        max_retries=0,
        rate_limiter=AsyncRateLimiter(0),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        ),
    )
    try:
        with pytest.raises(OzonRequestError) as exc_info:
            await client.send_review_answer("review-id", "Спасибо за отзыв!")
    finally:
        await client.aclose()

    assert exc_info.value.status_code == 400
    assert "review is not commentable" in exc_info.value.detail


@pytest.mark.asyncio
async def test_network_error_detail_contains_exception_type() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connect timed out")

    client = OzonClient(
        "https://example.test",
        "client-id",
        "api-key",
        max_retries=0,
        rate_limiter=AsyncRateLimiter(0),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        ),
    )
    try:
        with pytest.raises(OzonRequestError) as exc_info:
            await client.count_reviews()
    finally:
        await client.aclose()

    assert exc_info.value.status_code == 0
    assert "ConnectTimeout" in exc_info.value.detail
