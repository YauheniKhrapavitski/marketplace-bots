from typing import Any

import pytest

from app.bot.middlewares import AdminOnlyMiddleware
from app.config import Settings


class FakeEvent:
    def __init__(self) -> None:
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


@pytest.mark.asyncio
async def test_admin_middleware_rejects_unknown_user() -> None:
    settings = Settings(
        telegram_admin_ids="1",
        app_encryption_key="test-encryption-key",
        telegram_bot_token="test-token",  # noqa: S106
    )
    middleware = AdminOnlyMiddleware(settings)
    event = FakeEvent()
    called = False

    async def handler(_: Any, __: dict[str, Any]) -> None:
        nonlocal called
        called = True

    await middleware(handler, event, {"event_from_user": FakeUser(2)})  # type: ignore[arg-type]
    assert not called
    assert event.answers == ["У вас нет доступа к этому боту"]
