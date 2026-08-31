from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.methods import DeleteWebhook, GetUpdates

from app.bot.factory import create_bot, create_dispatcher, setup_bot_commands
from app.config import get_settings
from app.db.session import SessionFactory
from app.logging import configure_logging
from app.repositories.ozon_review_repository import OzonReviewRepository
from app.workers.scheduler import create_scheduler, scheduler_state

logger = logging.getLogger(__name__)
_update_tasks: set[asyncio.Task[object]] = set()


async def _prepare_telegram_without_blocking_startup(bot: Bot) -> None:
    try:
        await bot(DeleteWebhook(drop_pending_updates=False), request_timeout=15)
        await setup_bot_commands(bot, ozon_only=True)
    except Exception:
        logger.warning(
            "telegram command setup failed",
            exc_info=True,
            extra={"service": "telegram", "event": "telegram_command_setup_failed"},
        )


async def _run_polling_with_retries(bot: Bot, dispatcher: Dispatcher) -> None:
    offset: int | None = None
    while True:
        try:
            updates = await bot(
                GetUpdates(
                    offset=offset,
                    timeout=30,
                    allowed_updates=["message", "callback_query"],
                ),
                request_timeout=45,
            )
            for update in updates:
                offset = update.update_id + 1
                logger.info(
                    "Telegram update received",
                    extra={"service": "telegram", "event": "telegram_update_received"},
                )
                update_task = asyncio.create_task(dispatcher.feed_update(bot, update))
                _update_tasks.add(update_task)
                update_task.add_done_callback(_update_tasks.discard)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "telegram polling failed",
                extra={"service": "telegram", "event": "telegram_polling_failed"},
            )
            await asyncio.sleep(15)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    scheduler = create_scheduler(settings)
    scheduler.start()
    scheduler_state.running = True

    async with SessionFactory() as session:
        await OzonReviewRepository(session).restore_sending()
        await session.commit()

    bot = create_bot(settings.ozon_telegram_bot_token)
    telegram_prepare_task = asyncio.create_task(_prepare_telegram_without_blocking_startup(bot))
    dispatcher = create_dispatcher(settings, ozon_only=True)

    try:
        logger.info("Start polling", extra={"service": "app", "event": "Start polling"})
        await _run_polling_with_retries(bot, dispatcher)
    finally:
        scheduler.shutdown(wait=False)
        scheduler_state.running = False
        if not telegram_prepare_task.done():
            telegram_prepare_task.cancel()
        for update_task in _update_tasks:
            if not update_task.done():
                update_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
