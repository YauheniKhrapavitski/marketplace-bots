from dataclasses import dataclass

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import Settings
from app.workers.ozon_review_sync_job import run_ozon_review_sync_once
from app.workers.question_sync_job import run_question_sync_once
from app.workers.sync_job import run_sync_once


@dataclass
class SchedulerState:
    running: bool = False


scheduler_state = SchedulerState()


def create_scheduler(settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    if settings.feedback_scheduler_enabled:
        scheduler.add_job(
            run_sync_once,
            "interval",
            minutes=settings.sync_interval_minutes,
            id="feedback_sync",
            max_instances=1,
            coalesce=True,
        )
    if settings.question_scheduler_enabled and not settings.feedback_scheduler_enabled:
        scheduler.add_job(
            run_question_sync_once,
            "interval",
            minutes=settings.sync_interval_minutes,
            id="question_sync",
            max_instances=1,
            coalesce=True,
        )
    if settings.ozon_client_id and settings.ozon_api_key:
        scheduler.add_job(
            run_ozon_review_sync_once,
            "interval",
            minutes=settings.sync_interval_minutes,
            id="ozon_review_sync",
            max_instances=1,
            coalesce=True,
        )
    return scheduler
