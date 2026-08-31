from __future__ import annotations

import asyncio
import logging

from app.bot.factory import create_bot, create_dispatcher, setup_bot_commands
from app.config import get_settings
from app.db.session import SessionFactory
from app.logging import configure_logging
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.ozon_review_repository import OzonReviewRepository
from app.repositories.question_repository import QuestionRepository
from app.workers.scheduler import create_scheduler, scheduler_state

logger = logging.getLogger(__name__)


async def _setup_bot_commands_without_blocking_startup(bot) -> None:
    try:
        await setup_bot_commands(bot)
    except Exception:
        logger.warning(
            "telegram command setup failed",
            exc_info=True,
            extra={"service": "telegram", "event": "telegram_command_setup_failed"},
        )


async def _run_polling_with_retries(polling_factory) -> None:
    while True:
        try:
            await polling_factory()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "telegram polling failed",
                extra={"service": "telegram", "event": "telegram_polling_failed"},
            )
        else:
            logger.warning(
                "telegram polling stopped",
                extra={"service": "telegram", "event": "telegram_polling_stopped"},
            )
        await asyncio.sleep(15)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    scheduler = create_scheduler(settings)
    scheduler.start()
    scheduler_state.running = True

    async with SessionFactory() as session:
        await FeedbackRepository(session).restore_sending()
        await QuestionRepository(session).restore_sending()
        await OzonReviewRepository(session).restore_sending()
        await session.commit()

    bot = create_bot(settings.telegram_bot_token)
    command_task = asyncio.create_task(_setup_bot_commands_without_blocking_startup(bot))
    dispatcher = create_dispatcher(settings)

    try:
        logger.info("Start polling", extra={"service": "app", "event": "Start polling"})
        await _run_polling_with_retries(
            lambda: dispatcher.start_polling(bot, polling_timeout=30)
        )
    finally:
        scheduler.shutdown(wait=False)
        scheduler_state.running = False
        if not command_task.done():
            command_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
