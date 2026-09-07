from __future__ import annotations

import asyncio
import logging
import shutil
import socket
import time
from pathlib import Path

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand

from ttn_bot.bot import BotContext, build_dispatcher
from ttn_bot.config import get_settings
from ttn_bot.storage import Storage
from ttn_bot.template import load_template


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_old_temp_dirs(settings.temp_dir, settings.temp_file_lifetime_hours)
    storage = Storage(settings.database_path)
    storage.init()
    template = load_template(settings.ttn_template_path)
    context = BotContext(
        settings=settings,
        storage=storage,
        template=template,
        semaphore=asyncio.Semaphore(settings.max_concurrent_jobs),
    )
    session = AiohttpSession(timeout=30)
    session._connector_init["family"] = socket.AF_INET
    bot = Bot(settings.bot_token, session=session)
    await _set_bot_commands_without_blocking_startup(bot)
    dispatcher = build_dispatcher(context)
    await _run_polling_with_retries(lambda: dispatcher.start_polling(bot, polling_timeout=20))


def _cleanup_old_temp_dirs(temp_dir: Path, lifetime_hours: int) -> None:
    if lifetime_hours <= 0 or not temp_dir.exists():
        return
    cutoff = time.time() - lifetime_hours * 3600
    for child in temp_dir.glob("*/*"):
        try:
            if child.is_dir() and child.stat().st_mtime < cutoff:
                shutil.rmtree(child, ignore_errors=True)
        except OSError:
            logging.getLogger(__name__).warning("Could not inspect temp path %s", child)


async def _set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Начать работу"),
            BotCommand(command="new", description="Обработать новую ТТН"),
            BotCommand(command="template", description="Показать пустой шаблон"),
            BotCommand(command="my_template", description="Показать сохранённый шаблон"),
            BotCommand(command="delete_template", description="Удалить сохранённый шаблон"),
            BotCommand(command="cancel", description="Отменить текущую операцию"),
            BotCommand(command="help", description="Инструкция"),
        ]
    )


async def _set_bot_commands_without_blocking_startup(bot: Bot) -> None:
    try:
        await _set_bot_commands(bot)
    except Exception:
        logging.getLogger(__name__).warning("Telegram command setup failed", exc_info=True)


async def _run_polling_with_retries(polling_factory) -> None:
    while True:
        try:
            await polling_factory()
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger(__name__).exception("Telegram polling failed")
        else:
            logging.getLogger(__name__).warning("Telegram polling stopped")
        await asyncio.sleep(15)


if __name__ == "__main__":
    asyncio.run(main())
