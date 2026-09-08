import logging
import re
from datetime import UTC, datetime
from math import ceil

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, ForceReply, Message

from app.bot.keyboards.reviews import review_keyboard, skip_keyboard
from app.bot.messages.reviews import format_feedback_card
from app.config import get_settings
from app.db.session import SessionFactory
from app.integrations.wildberries.client import WildberriesClient
from app.integrations.wildberries.exceptions import (
    WildberriesAuthError,
    WildberriesRateLimitError,
    WildberriesRequestError,
)
from app.repositories.account_repository import AccountRepository
from app.repositories.action_repository import ActionRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.services.encryption_service import EncryptionService
from app.services.feedback_service import FeedbackService

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("reviews"))
async def reviews(message: Message) -> None:
    await send_next_review(message)


@router.message(F.reply_to_message, F.text.regexp(r"^(?!/)"))
async def answer_reply(message: Message) -> None:
    if message.reply_to_message is None or not message.reply_to_message.text:
        return
    match = re.search(r"Отзыв #(\d+)", message.reply_to_message.text)
    if match is None:
        return
    await save_manual_answer(message, int(match.group(1)), message.text or "")


@router.message(F.text.regexp(r"^/review_answer_\d+(\s|$)"))
async def answer_command(message: Message) -> None:
    text = message.text or ""
    command, _, answer_text = text.partition(" ")
    feedback_id = int(command.removeprefix("/review_answer_"))
    answer_text = answer_text.strip()
    if not answer_text:
        await message.answer(
            f"Отправьте текст так:\n"
            f"/review_answer_{feedback_id} Здравствуйте, ваш ответ покупателю"
        )
        return
    await save_manual_answer(message, feedback_id, answer_text)


async def save_manual_answer(message: Message, feedback_id: int, answer_text: str) -> None:
    answer_text = answer_text.strip()
    if not answer_text:
        await message.answer("Ответ пустой. Напишите текст ответа покупателю.")
        return
    if message.from_user is None:
        await message.answer("Не удалось определить оператора Telegram.")
        return
    async with SessionFactory() as session:
        service = FeedbackService(FeedbackRepository(session), ActionRepository(session))
        feedback = await service.edit_answer(feedback_id, answer_text, message.from_user.id)
        await session.commit()
        await message.answer(
            "Ответ сохранен. Проверьте текст и нажмите «Отправить ответ», когда будете готовы."
        )
        url = (
            f"https://www.wildberries.ru/catalog/{feedback.nm_id}/detail.aspx"
            if feedback.nm_id
            else None
        )
        await message.answer(
            format_feedback_card(feedback), reply_markup=review_keyboard(feedback.id, url)
        )


@router.message(Command("sync"))
async def sync(message: Message) -> None:
    await run_review_sync(message, retry_command="/sync", show_next=False)


@router.message(Command("process_reviews"))
async def process_reviews(message: Message) -> None:
    await run_review_sync(message, retry_command="/process_reviews", show_next=True)


@router.message(Command("archive_old_reviews"))
async def archive_old_reviews(message: Message) -> None:
    before = _archive_before_from_message(message)
    async with SessionFactory() as session:
        archived_count = await FeedbackRepository(session).archive_pending_before(before)
        queue_count = await FeedbackRepository(session).count_queue()
        await session.commit()
    await message.answer(
        f"Старые отзывы до {before.date().isoformat()} убраны из очереди: "
        f"{archived_count}. Осталось в очереди: {queue_count}."
    )


async def run_review_sync(
    message: Message, *, retry_command: str, show_next: bool
) -> None:
    from app.workers.sync_job import run_sync_once

    await message.answer("Синхронизация началась. Проверяю новые отзывы Wildberries.")
    try:
        received, created, updated = await run_sync_once()
    except WildberriesAuthError:
        await message.answer(
            "Wildberries отклонил API-токен. Проверьте, что в .env.wb указан свежий "
            "production-токен с доступом к категории «Вопросы и отзывы», "
            f"и повторите {retry_command}."
        )
        raise
    except WildberriesRateLimitError as exc:
        await message.answer(_wb_rate_limit_message(exc, retry_command))
        return
    except WildberriesRequestError as exc:
        await message.answer(_wb_request_error_message(exc, retry_command))
        raise
    except Exception:
        logger.exception("Unexpected WB sync error")
        await message.answer(
            "Синхронизация не завершилась из-за внутренней ошибки бота. "
            "Проверьте свежие логи wb-bot на VPS."
        )
        raise
    async with SessionFactory() as session:
        queue_count = await FeedbackRepository(session).count_queue()
    await message.answer(
        f"Синхронизация завершена: получено {received}, новых {created}, "
        f"обновлено {updated}. Очередь к ручной проверке: {queue_count}"
    )
    if show_next and queue_count:
        await send_next_review(message)


@router.callback_query(F.data == "review:next")
async def next_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await send_next_review(callback.message)


@router.callback_query(F.data.startswith("review:send:"))
async def send_callback(callback: CallbackQuery) -> None:
    feedback_id = int(callback.data.split(":")[-1]) if callback.data else 0
    settings = get_settings()
    async with SessionFactory() as session:
        account = await AccountRepository(session).get_active()
        if account is None:
            await callback.answer("Wildberries не подключён", show_alert=True)
            return
        token = EncryptionService(settings.app_encryption_key).decrypt(account.encrypted_api_token)
        client = WildberriesClient(
            settings.wb_api_base_url,
            token,
            max_retries=settings.http_max_retries,
            min_interval_seconds=settings.wb_api_min_interval_seconds,
        )
        try:
            service = FeedbackService(
                FeedbackRepository(session),
                ActionRepository(session),
                client,
            )
            await service.send_answer(feedback_id, callback.from_user.id)
            await session.commit()
        finally:
            await client.aclose()
    await callback.answer("Ответ успешно отправлен", show_alert=True)


@router.callback_query(F.data.startswith("review:skip:"))
async def skip_callback(callback: CallbackQuery) -> None:
    feedback_id = int(callback.data.split(":")[-1]) if callback.data else 0
    if callback.message:
        await callback.message.answer("Выберите действие", reply_markup=skip_keyboard(feedback_id))
    await callback.answer()


@router.callback_query(F.data.startswith("review:postpone:"))
async def postpone_callback(callback: CallbackQuery) -> None:
    feedback_id = int(callback.data.split(":")[-1]) if callback.data else 0
    async with SessionFactory() as session:
        await FeedbackService(FeedbackRepository(session), ActionRepository(session)).postpone(
            feedback_id, get_settings().postpone_hours, callback.from_user.id
        )
        await session.commit()
    await callback.answer("Отзыв вернётся позже", show_alert=True)


@router.callback_query(F.data.startswith("review:ignore:"))
async def ignore_callback(callback: CallbackQuery) -> None:
    feedback_id = int(callback.data.split(":")[-1]) if callback.data else 0
    async with SessionFactory() as session:
        await FeedbackService(FeedbackRepository(session), ActionRepository(session)).ignore(
            feedback_id, callback.from_user.id
        )
        await session.commit()
    await callback.answer("Отзыв помечен без ответа", show_alert=True)


@router.callback_query(F.data.startswith("review:edit:"))
async def edit_callback(callback: CallbackQuery) -> None:
    feedback_id = int(callback.data.split(":")[-1]) if callback.data else 0
    await ask_for_custom_answer(callback, feedback_id)


@router.callback_query(F.data.startswith("review:custom:"))
async def custom_callback(callback: CallbackQuery) -> None:
    feedback_id = int(callback.data.split(":")[-1]) if callback.data else 0
    await ask_for_custom_answer(callback, feedback_id)


async def ask_for_custom_answer(callback: CallbackQuery, feedback_id: int) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"Отзыв #{feedback_id}\n"
            "Напишите свой вариант ответа одним сообщением.",
            reply_markup=ForceReply(
                input_field_placeholder="Здравствуйте, ",
                selective=True,
            ),
        )


def _wb_rate_limit_message(exc: WildberriesRateLimitError, action: str) -> str:
    seconds = exc.retry_after_seconds or 720
    minutes = max(1, ceil(seconds / 60))
    return (
        "Wildberries ограничил частоту запросов для категории «Вопросы и отзывы». "
        f"Подождите примерно {minutes} мин. и повторите {action}."
    )


def _wb_request_error_message(exc: WildberriesRequestError, action: str) -> str:
    if exc.status_code == 0:
        return (
            "Не удалось подключиться к Wildberries API. Проверьте сеть/DNS на VPS "
            f"и повторите {action}."
        )
    return (
        f"Wildberries API вернул ошибку HTTP {exc.status_code}. "
        f"Повторите {action} позже или проверьте настройки WB API."
    )


def _archive_before_from_message(message: Message) -> datetime:
    text = message.text or ""
    _, _, raw_date = text.partition(" ")
    if not raw_date.strip():
        return datetime(2026, 9, 1, tzinfo=UTC)
    try:
        return datetime.fromisoformat(raw_date.strip()).replace(tzinfo=UTC)
    except ValueError:
        return datetime(2026, 9, 1, tzinfo=UTC)


@router.callback_query(F.data.startswith("review:template:"))
async def template_callback(callback: CallbackQuery) -> None:
    await callback.answer("Выбор шаблона доступен через /templates", show_alert=True)


async def send_next_review(message: Message) -> None:
    async with SessionFactory() as session:
        feedback = await FeedbackRepository(session).next_pending()
        if feedback is None:
            await message.answer("Новых отзывов для обработки нет")
            return
        url = (
            f"https://www.wildberries.ru/catalog/{feedback.nm_id}/detail.aspx"
            if feedback.nm_id
            else None
        )
        await message.answer(
            format_feedback_card(feedback), reply_markup=review_keyboard(feedback.id, url)
        )
