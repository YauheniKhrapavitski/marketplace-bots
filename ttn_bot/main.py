from __future__ import annotations

import asyncio
import logging
import shutil
import time
from pathlib import Path

from aiogram import Bot
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
    bot = Bot(settings.bot_token)
    await _set_bot_commands(bot)
    dispatcher = build_dispatcher(context)
    await dispatcher.start_polling(bot)


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


if __name__ == "__main__":
    asyncio.run(main())
