import asyncio

import pytest

from app.workers import ozon_review_sync_job


@pytest.mark.asyncio
async def test_concurrent_ozon_sync_calls_share_one_task(monkeypatch: pytest.MonkeyPatch) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    call_count = 0

    async def fake_sync() -> tuple[int, int, int]:
        nonlocal call_count
        call_count += 1
        started.set()
        await release.wait()
        return (3, 2, 1)

    monkeypatch.setattr(ozon_review_sync_job, "_active_sync_task", None)
    monkeypatch.setattr(ozon_review_sync_job, "_execute_ozon_review_sync_once", fake_sync)

    first = asyncio.create_task(ozon_review_sync_job.run_ozon_review_sync_once())
    await started.wait()
    second = asyncio.create_task(ozon_review_sync_job.run_ozon_review_sync_once())
    release.set()

    assert await asyncio.gather(first, second) == [(3, 2, 1), (3, 2, 1)]
    assert call_count == 1
