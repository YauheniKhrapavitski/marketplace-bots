import httpx
import pytest

from app.integrations.wildberries.client import WildberriesClient
from app.integrations.wildberries.exceptions import WildberriesAuthError, WildberriesRateLimitError
from app.integrations.wildberries.questions_client import WildberriesQuestionsClient
from app.integrations.wildberries.rate_limiter import AsyncRateLimiter


@pytest.fixture(autouse=True)
def reset_rate_limit_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(WildberriesClient, "_rate_limit_cooldown_until", 0.0)
    monkeypatch.setattr(WildberriesQuestionsClient, "_rate_limit_cooldown_until", 0.0)


@pytest.mark.asyncio
async def test_get_unanswered_feedbacks_parses_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("asyncio.sleep", no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "token"
        return httpx.Response(
            200,
            json={
                "data": {
                    "feedbacks": [
                        {
                            "id": "fb1",
                            "productValuation": 5,
                            "text": "ok",
                            "productDetails": {"nmId": 123, "productName": "Item"},
                        }
                    ]
                }
            },
        )

    client = WildberriesClient(
        "https://example.test",
        "token",
        rate_limiter=AsyncRateLimiter(0),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        ),
    )
    try:
        feedbacks = await client.get_unanswered_feedbacks(1, 0)
    finally:
        await client.aclose()
    assert feedbacks[0].id == "fb1"
    assert feedbacks[0].nm_id == 123


@pytest.mark.asyncio
async def test_429_stops_without_retry() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"X-Ratelimit-Retry": "29"}, json={})

    client = WildberriesClient(
        "https://example.test",
        "token",
        max_retries=2,
        rate_limiter=AsyncRateLimiter(0),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        ),
    )
    try:
        with pytest.raises(WildberriesRateLimitError):
            await client.get_unanswered_feedbacks(1, 0)
    finally:
        await client.aclose()
    assert calls == 1


@pytest.mark.asyncio
async def test_successful_request_waits_between_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"data": {"feedbacks": []}})

    client = WildberriesClient(
        "https://example.test",
        "token",
        min_interval_seconds=720,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        ),
    )
    try:
        await client.get_unanswered_feedbacks(1, 0)
        await client.get_unanswered_feedbacks(1, 0)
    finally:
        await client.aclose()

    assert calls == 2
    assert sleeps
    assert sleeps[0] > 700


@pytest.mark.asyncio
async def test_question_rate_limit_does_not_block_feedback_client() -> None:
    def question_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"X-Ratelimit-Retry": "29"}, json={})

    def feedback_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"feedbacks": []}})

    question_client = WildberriesQuestionsClient(
        "https://example.test",
        "token",
        rate_limiter=AsyncRateLimiter(0),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(question_handler), base_url="https://example.test"
        ),
    )
    feedback_client = WildberriesClient(
        "https://example.test",
        "token",
        rate_limiter=AsyncRateLimiter(0),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(feedback_handler), base_url="https://example.test"
        ),
    )
    try:
        with pytest.raises(WildberriesRateLimitError):
            await question_client.get_unanswered_questions(1, 0)
        assert await feedback_client.get_unanswered_feedbacks(1, 0) == []
    finally:
        await question_client.aclose()
        await feedback_client.aclose()


def test_retry_after_http_date_is_relative_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.time", lambda: 100.0)

    assert WildberriesClient._retry_after_seconds("Thu, 01 Jan 1970 00:02:00 GMT") == 20.0


def test_wb_retry_header_is_supported() -> None:
    assert WildberriesClient._retry_after_seconds("29") == 29.0


@pytest.mark.asyncio
async def test_401_is_not_retried() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={})

    client = WildberriesClient(
        "https://example.test",
        "token",
        max_retries=5,
        rate_limiter=AsyncRateLimiter(0),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        ),
    )
    with pytest.raises(WildberriesAuthError):
        await client.get_unanswered_feedbacks(1, 0)
    await client.aclose()
    assert calls == 1


@pytest.mark.asyncio
async def test_429_exhaustion() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    client = WildberriesClient(
        "https://example.test",
        "token",
        max_retries=0,
        rate_limiter=AsyncRateLimiter(0),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        ),
    )
    with pytest.raises(WildberriesRateLimitError):
        await client.get_unanswered_feedbacks(1, 0)
    await client.aclose()


@pytest.mark.asyncio
async def test_send_question_answer_uses_nested_answer_payload() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": None, "error": False})

    client = WildberriesQuestionsClient(
        "https://example.test",
        "token",
        rate_limiter=AsyncRateLimiter(0),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        ),
    )
    try:
        await client.send_question_answer("q1", "Ответ")
    finally:
        await client.aclose()

    assert requests[0].method == "PATCH"
    assert requests[0].url.path == "/api/v1/questions"
    assert requests[0].read().decode() == (
        '{"id":"q1","answer":{"text":"Ответ"},"state":"wbRu"}'
    )
