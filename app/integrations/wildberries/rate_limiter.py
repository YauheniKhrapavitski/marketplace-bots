import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class AsyncRateLimiter:
    def __init__(self, min_interval_seconds: float = 3.5) -> None:
        self._min_interval_seconds = min_interval_seconds
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def run(self, func: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            loop = asyncio.get_running_loop()
            elapsed = loop.time() - self._last_call
            if elapsed < self._min_interval_seconds:
                await asyncio.sleep(self._min_interval_seconds - elapsed)
            try:
                return await func()
            finally:
                self._last_call = loop.time()
