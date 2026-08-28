import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.api.health import router as health_router
from app.bot.factory import create_bot, create_dispatcher, setup_bot_commands
from app.config import get_settings
from app.db.session import SessionFactory
from app.logging import configure_logging
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.ozon_review_repository import OzonReviewRepository
from app.repositories.question_repository import QuestionRepository
from app.workers.scheduler import create_scheduler, scheduler_state

logger = logging.getLogger(__name__)


async def setup_bot_commands_without_blocking_startup(
    bot,
    *,
    questions_only: bool = False,
    ozon_only: bool = False,
    include_questions: bool = False,
) -> None:
    try:
        await setup_bot_commands(
            bot,
            questions_only=questions_only,
            ozon_only=ozon_only,
            include_questions=include_questions,
        )
    except Exception:
        logger.warning(
            "telegram command setup failed",
            exc_info=True,
            extra={"service": "telegram", "event": "telegram_command_setup_failed"},
        )


async def run_polling_with_retries(
    polling_factory: Callable[[], Awaitable[None]], bot_name: str
) -> None:
    while True:
        try:
            await polling_factory()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "telegram polling failed",
                extra={
                    "service": "telegram",
                    "event": "telegram_polling_failed",
                    "bot_name": bot_name,
                },
            )
        else:
            logger.warning(
                "telegram polling stopped",
                extra={
                    "service": "telegram",
                    "event": "telegram_polling_stopped",
                    "bot_name": bot_name,
                },
            )
        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    scheduler = create_scheduler(settings)
    scheduler.start()
    scheduler_state.running = True
    async with SessionFactory() as session:
        await FeedbackRepository(session).restore_sending()
        await QuestionRepository(session).restore_sending()
        await OzonReviewRepository(session).restore_sending()
        await session.commit()
    bot_task: asyncio.Task[None] | None = None
    questions_bot_task: asyncio.Task[None] | None = None
    ozon_bot_task: asyncio.Task[None] | None = None
    if settings.telegram_bot_token:
        bot = create_bot(settings.telegram_bot_token)
        await setup_bot_commands_without_blocking_startup(
            bot, include_questions=not bool(settings.questions_telegram_bot_token)
        )
        dispatcher = create_dispatcher(settings)
        bot_task = asyncio.create_task(
            run_polling_with_retries(
                lambda: dispatcher.start_polling(
                    bot, polling_timeout=0, close_bot_session=False
                ),
                "feedback",
            )
        )
    if settings.questions_telegram_bot_token:
        questions_bot = create_bot(settings.questions_telegram_bot_token)
        await setup_bot_commands_without_blocking_startup(questions_bot, questions_only=True)
        questions_dispatcher = create_dispatcher(settings, questions_only=True)
        questions_bot_task = asyncio.create_task(
            run_polling_with_retries(
                lambda: questions_dispatcher.start_polling(
                    questions_bot, polling_timeout=0, close_bot_session=False
                ),
                "questions",
            )
        )
    if settings.ozon_telegram_bot_token:
        ozon_bot = create_bot(settings.ozon_telegram_bot_token)
        await setup_bot_commands_without_blocking_startup(ozon_bot, ozon_only=True)
        ozon_dispatcher = create_dispatcher(settings, ozon_only=True)
        ozon_bot_task = asyncio.create_task(
            run_polling_with_retries(
                lambda: ozon_dispatcher.start_polling(
                    ozon_bot, polling_timeout=0, close_bot_session=False
                ),
                "ozon",
            )
        )
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        scheduler_state.running = False
        if bot_task:
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
        if questions_bot_task:
            questions_bot_task.cancel()
            try:
                await questions_bot_task
            except asyncio.CancelledError:
                pass
        if ozon_bot_task:
            ozon_bot_task.cancel()
            try:
                await ozon_bot_task
            except asyncio.CancelledError:
                pass


def create_app() -> FastAPI:
    app = FastAPI(title="WB Feedback Telegram Assistant", lifespan=lifespan)
    app.include_router(health_router)
    return app


app = create_app()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)  # noqa: S104


if __name__ == "__main__":
    main()
