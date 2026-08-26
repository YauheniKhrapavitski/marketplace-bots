import re
from datetime import UTC, datetime
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.config import get_settings
from app.db.models.ozon import OzonReview
from app.db.session import SessionFactory
from app.integrations.ozon.client import OzonClient
from app.integrations.ozon.exceptions import OzonAuthError, OzonRequestError
from app.repositories.ozon_account_repository import OzonAccountRepository
from app.repositories.ozon_review_action_repository import OzonReviewActionRepository
from app.repositories.ozon_review_repository import OzonReviewRepository
from app.repositories.ozon_review_template_repository import OzonReviewTemplateRepository
from app.services.encryption_service import EncryptionService
from app.services.ozon_review_service import OzonReviewService
from app.services.ozon_review_template_catalog import STARTER_OZON_REVIEW_TEMPLATES

router = Router()


@router.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer(
        "Бот отзывов Ozon. Используйте /ozon_sync, /ozon_reviews, "
        "/ozon_status и /ozon_templates."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "/ozon_status - статус интеграции Ozon\n"
        "/ozon_sync - синхронизировать отзывы Ozon\n"
        "/ozon_reviews - показать следующий отзыв Ozon\n"
        "/ozon_templates - список шаблонов ответов Ozon\n"
        "/ozon_roles - проверить роли API-ключа Ozon"
    )


@router.message(Command("ozon_status"))
async def ozon_status(message: Message) -> None:
    async with SessionFactory() as session:
        account = await OzonAccountRepository(session).get_active()
        reviews = OzonReviewRepository(session)
        queue_count = await reviews.count_queue()
        answered_today = await reviews.count_answered_since(
            datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        )
        last_sync = (
            account.last_successful_sync_at.isoformat()
            if account and account.last_successful_sync_at
            else "none"
        )
        last_error = account.last_sync_error if account and account.last_sync_error else "none"
    await message.answer(
        "Статус отзывов Ozon\n"
        f"Ozon подключен: {'да' if account else 'нет'}\n"
        f"Последняя успешная синхронизация: {last_sync}\n"
        f"Очередь отзывов: {queue_count}\n"
        f"Ответов за сегодня: {answered_today}\n"
        f"Последняя ошибка: {last_error}"
    )


@router.message(Command("ozon_sync"))
async def ozon_sync(message: Message) -> None:
    from app.workers.ozon_review_sync_job import run_ozon_review_sync_once

    await message.answer("Синхронизация отзывов Ozon началась.")
    try:
        received, created, updated = await run_ozon_review_sync_once()
    except OzonAuthError:
        await message.answer(
            "Синхронизация Ozon не выполнена: Ozon вернул 403 Forbidden. "
            "Проверьте Client-Id, Api-Key и доступ аккаунта к API отзывов."
        )
        return
    except OzonRequestError as exc:
        await message.answer(_format_ozon_request_error(exc))
        return
    except Exception:
        await message.answer("Синхронизация Ozon не выполнена из-за неожиданной ошибки.")
        return
    await message.answer(
        f"Синхронизация Ozon завершена: получено {received}, новых {created}, "
        f"обновлено {updated}"
    )


@router.message(Command("ozon_reviews"))
async def ozon_reviews(message: Message) -> None:
    await send_next_ozon_review(message)


@router.message(Command("ozon_templates"))
async def ozon_templates(message: Message) -> None:
    async with SessionFactory() as session:
        repo = OzonReviewTemplateRepository(session)
        await repo.seed(STARTER_OZON_REVIEW_TEMPLATES)
        templates = await repo.list_active_candidates()
        await session.commit()
    rows = [
        f"{template.code}: {'авто' if template.auto_send else 'ручное подтверждение'}"
        for template in templates
    ]
    await message.answer("Шаблоны Ozon\n" + "\n".join(rows))


@router.message(Command("ozon_roles"))
async def ozon_roles(message: Message) -> None:
    settings = get_settings()
    async with SessionFactory() as session:
        account = await OzonAccountRepository(session).get_active()
        if account is None:
            await message.answer("Ozon не подключен.")
            return
        api_key = EncryptionService(settings.app_encryption_key).decrypt(account.encrypted_api_key)
    client = OzonClient(
        settings.ozon_api_base_url,
        account.client_id,
        api_key,
        max_retries=settings.ozon_http_max_retries,
        connect_timeout=settings.ozon_http_connect_timeout,
        read_timeout=settings.ozon_http_read_timeout,
    )
    try:
        roles = await client.get_roles()
    except OzonAuthError:
        await message.answer("Ozon вернул 403 Forbidden при проверке ролей API-ключа.")
        return
    except OzonRequestError as exc:
        await message.answer(
            _format_ozon_request_error(exc, action="Не удалось проверить роли Ozon")
        )
        return
    finally:
        await client.aclose()
    await message.answer("Роли API-ключа Ozon\n" + _format_roles(roles))


@router.message(F.reply_to_message, F.text.regexp(r"^(?!/)"))
async def answer_reply(message: Message) -> None:
    if message.reply_to_message is None or not message.reply_to_message.text:
        return
    match = re.search(r"Отзыв Ozon #(\d+)", message.reply_to_message.text)
    if match is None:
        return
    await save_manual_answer(message, int(match.group(1)), message.text or "")


@router.message(F.text.regexp(r"^/ozon_answer_\d+(\s|$)"))
async def answer_command(message: Message) -> None:
    text = message.text or ""
    command, _, answer_text = text.partition(" ")
    review_id = int(command.removeprefix("/ozon_answer_"))
    if not answer_text.strip():
        await message.answer(
            f"Отправьте текст так:\n/ozon_answer_{review_id} Здравствуйте, ..."
        )
        return
    await save_manual_answer(message, review_id, answer_text)


async def save_manual_answer(message: Message, review_id: int, answer_text: str) -> None:
    answer_text = answer_text.strip()
    if not answer_text:
        await message.answer("Ответ пустой. Отправьте текст ответа одним сообщением.")
        return
    if message.from_user is None:
        await message.answer("Не удалось определить оператора Telegram.")
        return
    async with SessionFactory() as session:
        service = OzonReviewService(
            OzonReviewRepository(session), OzonReviewActionRepository(session)
        )
        review = await service.edit_answer(review_id, answer_text, message.from_user.id)
        await session.commit()
        await message.answer(
            "Ответ сохранен. Проверьте текст и нажмите «Отправить ответ», когда будете готовы."
        )
        url = f"https://www.ozon.ru/product/{review.sku}/" if review.sku else None
        await message.answer(
            format_ozon_review_card(review), reply_markup=ozon_review_keyboard(review, url)
        )


@router.callback_query(F.data == "ozon_review:next")
async def next_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await send_next_ozon_review(callback.message)


@router.callback_query(F.data.startswith("ozon_review:send:"))
async def send_callback(callback: CallbackQuery) -> None:
    review_id = int(callback.data.split(":")[-1]) if callback.data else 0
    settings = get_settings()
    async with SessionFactory() as session:
        account = await OzonAccountRepository(session).get_active()
        if account is None:
            await callback.answer("Ozon не подключен", show_alert=True)
            return
        api_key = EncryptionService(settings.app_encryption_key).decrypt(account.encrypted_api_key)
        client = OzonClient(
            settings.ozon_api_base_url,
            account.client_id,
            api_key,
            max_retries=settings.ozon_http_max_retries,
            connect_timeout=settings.ozon_http_connect_timeout,
            read_timeout=settings.ozon_http_read_timeout,
        )
        try:
            service = OzonReviewService(
                OzonReviewRepository(session),
                OzonReviewActionRepository(session),
                client,
            )
            await service.send_answer(review_id, callback.from_user.id)
            await session.commit()
        finally:
            await client.aclose()
    await callback.answer("Ответ Ozon отправлен", show_alert=True)


@router.callback_query(F.data.startswith("ozon_review:edit:"))
async def edit_callback(callback: CallbackQuery) -> None:
    review_id = int(callback.data.split(":")[-1]) if callback.data else 0
    await ask_for_custom_ozon_answer(callback, review_id)


@router.callback_query(F.data.startswith("ozon_review:custom:"))
async def custom_callback(callback: CallbackQuery) -> None:
    review_id = int(callback.data.split(":")[-1]) if callback.data else 0
    await ask_for_custom_ozon_answer(callback, review_id)


@router.callback_query(F.data.startswith("ozon_review:template:"))
async def template_callback(callback: CallbackQuery) -> None:
    await callback.answer("Выбор шаблона доступен через /ozon_templates", show_alert=True)


async def ask_for_custom_ozon_answer(callback: CallbackQuery, review_id: int) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"Отзыв Ozon #{review_id}\n"
            "Напишите свой вариант ответа одним сообщением.",
            reply_markup=ForceReply(
                input_field_placeholder="Здравствуйте, ",
                selective=True,
            ),
        )


@router.callback_query(F.data.startswith("ozon_review:skip:"))
async def skip_callback(callback: CallbackQuery) -> None:
    review_id = int(callback.data.split(":")[-1]) if callback.data else 0
    if callback.message:
        await callback.message.answer(
            "Выберите действие", reply_markup=ozon_review_skip_keyboard(review_id)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("ozon_review:postpone:"))
async def postpone_callback(callback: CallbackQuery) -> None:
    review_id = int(callback.data.split(":")[-1]) if callback.data else 0
    async with SessionFactory() as session:
        await OzonReviewService(
            OzonReviewRepository(session), OzonReviewActionRepository(session)
        ).postpone(review_id, get_settings().postpone_hours, callback.from_user.id)
        await session.commit()
    await callback.answer("Отзыв Ozon отложен", show_alert=True)


@router.callback_query(F.data.startswith("ozon_review:ignore:"))
async def ignore_callback(callback: CallbackQuery) -> None:
    review_id = int(callback.data.split(":")[-1]) if callback.data else 0
    async with SessionFactory() as session:
        await OzonReviewService(
            OzonReviewRepository(session), OzonReviewActionRepository(session)
        ).ignore(review_id, callback.from_user.id)
        await session.commit()
    await callback.answer("Отзыв Ozon помечен без ответа", show_alert=True)


async def send_next_ozon_review(message: Message) -> None:
    async with SessionFactory() as session:
        review = await OzonReviewRepository(session).next_pending()
        if review is None:
            await message.answer("Новых отзывов Ozon для обработки нет.")
            return
        url = f"https://www.ozon.ru/product/{review.sku}/" if review.sku else None
        await message.answer(
            format_ozon_review_card(review), reply_markup=ozon_review_keyboard(review, url)
        )


def ozon_review_keyboard(
    review: OzonReview, product_url: str | None = None
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="Отправить ответ",
                callback_data=f"ozon_review:send:{review.id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="Редактировать", callback_data=f"ozon_review:edit:{review.id}"
            ),
            InlineKeyboardButton(
                text="Другой шаблон", callback_data=f"ozon_review:template:{review.id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="Свой вариант ответа", callback_data=f"ozon_review:custom:{review.id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="Пропустить", callback_data=f"ozon_review:skip:{review.id}"
            ),
            InlineKeyboardButton(text="Следующий отзыв", callback_data="ozon_review:next"),
        ],
    ]
    if product_url:
        rows.append([InlineKeyboardButton(text="Карточка товара", url=product_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ozon_review_skip_keyboard(review_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Вернуться позже", callback_data=f"ozon_review:postpone:{review_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Не отвечать", callback_data=f"ozon_review:ignore:{review_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отмена", callback_data=f"ozon_review:cancel:{review_id}"
                )
            ],
        ]
    )


@router.callback_query(F.data.startswith("ozon_review:cancel:"))
async def cancel_callback(callback: CallbackQuery) -> None:
    await callback.answer("Отменено", show_alert=True)


def format_ozon_review_card(review: OzonReview) -> str:
    lines = ["<b>Новый отзыв</b>", ""]
    _add_ozon_card_line(lines, "Товар", review.product_name)
    _add_ozon_card_line(lines, "Артикул Ozon", str(review.sku) if review.sku else None)
    _add_ozon_card_line(lines, "Offer ID", review.offer_id)
    _add_ozon_card_line(lines, "Оценка", f"{review.rating} из 5")
    _add_ozon_card_line(lines, "Покупатель", review.buyer_name)
    _add_ozon_card_line(
        lines,
        "Дата",
        review.published_at_ozon.isoformat() if review.published_at_ozon else None,
    )
    _add_ozon_card_block(lines, "Отзыв", review.review_text)
    _add_ozon_card_block(lines, "Достоинства", review.pros)
    _add_ozon_card_block(lines, "Недостатки", review.cons)
    _add_ozon_card_block(lines, "Предлагаемый ответ", review.answer_text)
    return "\n".join(lines)


def _add_ozon_card_line(lines: list[str], label: str, value: str | None) -> None:
    if value:
        lines.append(f"<b>{escape(label)}:</b> {escape(value)}")


def _add_ozon_card_block(lines: list[str], label: str, value: str | None) -> None:
    if value:
        lines.extend(["", f"<b>{escape(label)}:</b>", escape(value)])


def _format_roles(payload: dict[str, object]) -> str:
    text = str(payload)
    if len(text) > 3000:
        return text[:3000] + "..."
    return text


def _format_ozon_request_error(
    exc: OzonRequestError, *, action: str = "Синхронизация Ozon не выполнена"
) -> str:
    if exc.status_code == 0:
        detail = f"\nДеталь: {exc.detail}" if exc.detail else ""
        return (
            f"{action}: сетевая ошибка или таймаут API. "
            "Проверьте доступ к api-seller.ozon.ru и повторите попытку."
            f"{detail}"
        )
    detail = f"\nОтвет Ozon: {exc.detail}" if exc.detail else ""
    return f"{action}: Ozon вернул HTTP {exc.status_code}.{detail}"
