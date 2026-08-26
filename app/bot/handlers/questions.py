import re
from datetime import UTC, datetime
from math import ceil

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
from app.db.models.question import Question
from app.db.session import SessionFactory
from app.integrations.wildberries.exceptions import WildberriesRateLimitError
from app.integrations.wildberries.questions_client import WildberriesQuestionsClient
from app.repositories.account_repository import AccountRepository
from app.repositories.question_action_repository import QuestionActionRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.question_template_repository import QuestionTemplateRepository
from app.services.encryption_service import EncryptionService
from app.services.question_service import QuestionService
from app.services.question_template_catalog import STARTER_QUESTION_TEMPLATES

router = Router()


@router.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer(
        "Бот помогает обрабатывать вопросы покупателей Wildberries отдельными шаблонами. "
        "Используйте /questions_sync, /questions и /questions_status."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "/start - главное меню\n"
        "/questions_status - статус вопросов покупателей\n"
        "/questions_sync - ручная синхронизация вопросов\n"
        "/questions - следующий вопрос для обработки\n"
        "/question_templates - список шаблонов для вопросов"
    )


@router.message(Command("questions_status"))
async def questions_status(message: Message) -> None:
    async with SessionFactory() as session:
        account = await AccountRepository(session).get_active()
        questions = QuestionRepository(session)
        queue_count = await questions.count_queue()
        answered_today = await questions.count_answered_since(
            datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        )
        last_sync = (
            account.last_successful_sync_at.isoformat()
            if account and account.last_successful_sync_at
            else "нет"
        )
        last_error = account.last_sync_error if account and account.last_sync_error else "нет"
    await message.answer(
        "Статус вопросов покупателей\n"
        f"Wildberries подключен: {'да' if account else 'нет'}\n"
        f"Последняя успешная синхронизация: {last_sync}\n"
        f"Очередь вопросов: {queue_count}\n"
        f"Ответов за сутки: {answered_today}\n"
        f"Последняя ошибка: {last_error}"
    )


@router.message(Command("questions_sync"))
async def questions_sync(message: Message) -> None:
    from app.workers.question_sync_job import run_question_sync_once

    await message.answer("Синхронизация вопросов началась. Проверяю новые вопросы Wildberries.")
    try:
        received, created, updated = await run_question_sync_once()
    except WildberriesRateLimitError as exc:
        await message.answer(_wb_rate_limit_message(exc, "/questions_sync"))
        raise
    except Exception:
        await message.answer(
            "Синхронизация вопросов не завершилась. Проверьте WB API-токен и повторите "
            "/questions_sync."
        )
        raise
    await message.answer(
        f"Синхронизация вопросов завершена: получено {received}, новых {created}, "
        f"обновлено {updated}"
    )


@router.message(Command("questions"))
async def questions(message: Message) -> None:
    await send_next_question(message)


@router.message(F.reply_to_message, F.text.regexp(r"^(?!/)"))
async def answer_reply(message: Message) -> None:
    if message.reply_to_message is None or not message.reply_to_message.text:
        return
    match = re.search(r"Вопрос #(\d+)", message.reply_to_message.text)
    if match is None:
        return
    await save_manual_answer(message, int(match.group(1)), message.text or "")


@router.message(F.text.regexp(r"^/answer_\d+(\s|$)"))
async def answer_command(message: Message) -> None:
    text = message.text or ""
    command, _, answer_text = text.partition(" ")
    question_id = int(command.removeprefix("/answer_"))
    answer_text = answer_text.strip()
    if not answer_text:
        await message.answer(
            f"Отправьте текст так:\n/answer_{question_id} Добрый день, ваш ответ покупателю"
        )
        return
    await save_manual_answer(message, question_id, answer_text)


async def save_manual_answer(message: Message, question_id: int, answer_text: str) -> None:
    answer_text = answer_text.strip()
    if not answer_text:
        await message.answer("Ответ пустой. Напишите текст ответа покупателю.")
        return
    if message.from_user is None:
        await message.answer("Не удалось определить оператора Telegram.")
        return
    async with SessionFactory() as session:
        service = QuestionService(QuestionRepository(session), QuestionActionRepository(session))
        question = await service.edit_answer(question_id, answer_text, message.from_user.id)
        await session.commit()
        await message.answer(
            "Ответ сохранен. Проверьте текст и нажмите «Отправить ответ», когда будете готовы."
        )
        await message.answer(
            format_question_card(question), reply_markup=question_keyboard(question)
        )


@router.message(Command("question_templates"))
async def question_templates(message: Message) -> None:
    async with SessionFactory() as session:
        repo = QuestionTemplateRepository(session)
        await repo.seed(STARTER_QUESTION_TEMPLATES)
        templates = await repo.list_active_candidates()
        await session.commit()
    rows = [
        f"{template.name}: {'авто' if template.auto_send else 'ручное подтверждение'}"
        for template in templates
    ]
    await message.answer("Шаблоны вопросов\n" + "\n".join(rows))


@router.callback_query(F.data == "question:next")
@router.callback_query(F.data.startswith("question:next:"))
async def next_callback(callback: CallbackQuery) -> None:
    exclude_id = None
    if callback.data and callback.data.startswith("question:next:"):
        exclude_id = int(callback.data.split(":")[-1])
    await callback.answer()
    if isinstance(callback.message, Message):
        await send_next_question(callback.message, exclude_id=exclude_id)


@router.callback_query(F.data.startswith("question:send:"))
async def send_callback(callback: CallbackQuery) -> None:
    question_id = int(callback.data.split(":")[-1]) if callback.data else 0
    settings = get_settings()
    async with SessionFactory() as session:
        account = await AccountRepository(session).get_active()
        if account is None:
            await callback.answer("Wildberries не подключен", show_alert=True)
            return
        token = EncryptionService(settings.app_encryption_key).decrypt(account.encrypted_api_token)
        client = WildberriesQuestionsClient(
            settings.wb_api_base_url,
            token,
            max_retries=settings.http_max_retries,
            min_interval_seconds=settings.wb_api_min_interval_seconds,
        )
        try:
            service = QuestionService(
                QuestionRepository(session),
                QuestionActionRepository(session),
                client,
            )
            await service.send_answer(question_id, callback.from_user.id)
            await session.commit()
        except WildberriesRateLimitError as exc:
            await session.commit()
            await callback.answer(
                _wb_rate_limit_message(exc, "Отправить ответ"),
                show_alert=True,
            )
            return
        finally:
            await client.aclose()
    await callback.answer("Ответ на вопрос отправлен", show_alert=True)
    if isinstance(callback.message, Message):
        await send_next_question(callback.message, exclude_id=question_id)


@router.callback_query(F.data.startswith("question:edit:"))
async def edit_callback(callback: CallbackQuery) -> None:
    question_id = int(callback.data.split(":")[-1]) if callback.data else 0
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"Вопрос #{question_id}\n"
            "Напишите свой ответ одним сообщением. Можно начать с: Добрый день,",
            reply_markup=ForceReply(
                input_field_placeholder="Добрый день, ",
                selective=True,
            ),
        )


@router.callback_query(F.data.startswith("question:ignore:"))
async def ignore_callback(callback: CallbackQuery) -> None:
    question_id = int(callback.data.split(":")[-1]) if callback.data else 0
    async with SessionFactory() as session:
        await QuestionService(
            QuestionRepository(session), QuestionActionRepository(session)
        ).ignore(question_id, callback.from_user.id)
        await session.commit()
    await callback.answer("Вопрос помечен без ответа", show_alert=True)
    if isinstance(callback.message, Message):
        await send_next_question(callback.message, exclude_id=question_id)


async def send_next_question(message: Message, exclude_id: int | None = None) -> None:
    async with SessionFactory() as session:
        question = await QuestionRepository(session).next_pending(exclude_id=exclude_id)
        if question is None:
            await message.answer("Новых вопросов для обработки нет")
            return
        await message.answer(
            format_question_card(question), reply_markup=question_keyboard(question)
        )


def question_keyboard(question: Question) -> InlineKeyboardMarkup:
    buttons = []
    if question.nm_id:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="Карточка товара",
                    url=f"https://www.wildberries.ru/catalog/{question.nm_id}/detail.aspx",
                )
            ]
        )
    if question.answer_text:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="Отправить ответ", callback_data=f"question:send:{question.id}"
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="Свой ответ", callback_data=f"question:edit:{question.id}"
            )
        ]
    )
    buttons.append(
        [
            InlineKeyboardButton(text="Без ответа", callback_data=f"question:ignore:{question.id}"),
            InlineKeyboardButton(text="Следующий", callback_data=f"question:next:{question.id}"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_question_card(question: Question) -> str:
    product = question.product_name or "товар не указан"
    article = question.supplier_article or "нет"
    answer = question.answer_text or "Тема не распознана. Нужна ручная обработка."
    return (
        f"Вопрос #{question.id}\n"
        f"Статус: {question.status}\n"
        f"Товар: {product}\n"
        f"Артикул: {article}\n"
        f"WB nmId: {question.nm_id or 'нет'}\n\n"
        f"Вопрос:\n{question.question_text}\n\n"
        f"Предложенный ответ:\n{answer}"
    )


def _wb_rate_limit_message(exc: WildberriesRateLimitError, action: str) -> str:
    seconds = exc.retry_after_seconds or 720
    minutes = max(1, ceil(seconds / 60))
    return (
        "Wildberries ограничил частоту запросов для категории «Вопросы и отзывы». "
        f"Подождите примерно {minutes} мин. и повторите {action}."
    )
