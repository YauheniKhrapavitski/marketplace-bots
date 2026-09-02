import socket

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app.bot.handlers import (
    common,
    history,
    ozon_reviews,
    questions,
    reviews,
    settings,
    status,
    templates,
)
from app.bot.middlewares import AdminOnlyMiddleware
from app.config import Settings


def create_dispatcher(
    settings_obj: Settings, *, questions_only: bool = False, ozon_only: bool = False
) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.message.middleware(AdminOnlyMiddleware(settings_obj))
    dispatcher.callback_query.middleware(AdminOnlyMiddleware(settings_obj))
    if ozon_only:
        dispatcher.include_router(ozon_reviews.router)
        return dispatcher
    if questions_only:
        dispatcher.include_router(questions.router)
        return dispatcher
    dispatcher.include_router(common.router)
    dispatcher.include_router(status.router)
    dispatcher.include_router(reviews.router)
    dispatcher.include_router(templates.router)
    dispatcher.include_router(settings.router)
    dispatcher.include_router(history.router)
    if not settings_obj.questions_telegram_bot_token:
        dispatcher.include_router(questions.router)
    return dispatcher


def create_bot(token: str) -> Bot:
    session = AiohttpSession(timeout=120)
    session._connector_init["family"] = socket.AF_INET
    return Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def setup_bot_commands(
    bot: Bot,
    *,
    questions_only: bool = False,
    ozon_only: bool = False,
    include_questions: bool = False,
) -> None:
    if ozon_only:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Ozon bot menu"),
                BotCommand(command="help", description="Список команд"),
                BotCommand(command="ozon_status", description="Статус отзывов Ozon"),
                BotCommand(command="ozon_sync", description="Синхронизировать отзывы Ozon"),
                BotCommand(command="ozon_reviews", description="Показать следующий отзыв Ozon"),
                BotCommand(command="ozon_templates", description="Шаблоны ответов Ozon"),
                BotCommand(command="ozon_roles", description="Проверить роли Ozon API"),
            ]
        )
        return
    if questions_only:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Главное меню"),
                BotCommand(command="help", description="Список команд"),
                BotCommand(command="questions_status", description="Статус вопросов покупателей"),
                BotCommand(command="questions_sync", description="Проверить новые вопросы"),
                BotCommand(command="questions", description="Показать следующий вопрос"),
                BotCommand(command="question_templates", description="Шаблоны для вопросов"),
            ]
        )
        return
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="status", description="Статус бота и интеграции"),
            BotCommand(command="sync", description="Проверить новые отзывы"),
            BotCommand(command="process_reviews", description="Обработать накопившиеся отзывы"),
            BotCommand(command="archive_old_reviews", description="Убрать старые отзывы"),
            BotCommand(command="reviews", description="Показать следующий отзыв"),
            BotCommand(command="templates", description="Шаблоны ответов на отзывы"),
            BotCommand(command="settings", description="Настройки интеграции"),
            BotCommand(command="history", description="Последние операции"),
        ]
        + (
            [
                BotCommand(command="questions_status", description="Статус вопросов покупателей"),
                BotCommand(command="questions_sync", description="Проверить новые вопросы"),
                BotCommand(command="questions", description="Показать следующий вопрос"),
                BotCommand(command="question_templates", description="Шаблоны для вопросов"),
            ]
            if include_questions
            else []
        )
    )
