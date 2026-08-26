from __future__ import annotations

import asyncio
import logging
import os
import shutil
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher, F, Router
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InaccessibleMessage, Message, TelegramObject

from ttn_bot.config import Settings
from ttn_bot.keyboards import fill_mode_keyboard, start_keyboard
from ttn_bot.models import (
    TtnEditData,
    empty_template_text,
    parse_edit_data_message,
    parse_series_and_number,
)
from ttn_bot.pdf.validator import PdfValidationError, validate_pdf
from ttn_bot.services import process_ttn_job
from ttn_bot.storage import Storage, template_to_user_text
from ttn_bot.template import TtnPdfTemplate

logger = logging.getLogger(__name__)


class TtnStates(StatesGroup):
    waiting_pdf = State()
    waiting_full_data = State()
    waiting_step_value = State()


STEP_FIELDS = [
    ("vehicle", "Введите автомобиль."),
    ("driver", "Введите водителя."),
    ("series_and_number", "Введите серию и номер ТТН, например: ЕМ 1926709."),
    ("release_allowed_by", "Кто разрешил отпуск?"),
]


HELP_TEXT = (
    "Загрузите исходную ТТН в PDF, затем отправьте заполненный шаблон данных одним сообщением "
    "или используйте пошаговый режим. "
    "Бот создаст новый заполненный PDF и Excel с данными накладной. "
    "Исходный PDF не изменяется."
)


@dataclass(frozen=True)
class BotContext:
    settings: Settings
    storage: Storage
    template: TtnPdfTemplate
    semaphore: asyncio.Semaphore


class AccessMiddleware(BaseMiddleware):
    def __init__(self, allowed_user_ids: list[int]) -> None:
        self.allowed_user_ids = allowed_user_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None and not _is_allowed(user.id, self.allowed_user_ids):
            if isinstance(event, Message):
                await event.answer("У вас нет доступа к этому боту.")
            elif isinstance(event, CallbackQuery):
                await event.answer("У вас нет доступа к этому боту.", show_alert=True)
            return None
        return await handler(event, data)


def build_dispatcher(context: BotContext) -> Dispatcher:
    router = Router()
    router.message.middleware(AccessMiddleware(context.settings.allowed_user_ids))
    router.callback_query.middleware(AccessMiddleware(context.settings.allowed_user_ids))

    @router.message(Command("start"))
    async def start(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(
            "Готов заполнить ТТН PDF и собрать Excel по товарным позициям.\n\n" + HELP_TEXT,
            reply_markup=start_keyboard(),
        )

    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer(HELP_TEXT)

    @router.message(Command("new"))
    async def new_command(message: Message, state: FSMContext) -> None:
        await _ask_pdf(message, state)

    @router.callback_query(F.data == "new_ttn")
    async def new_callback(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        _open_downloads_folder()
        if isinstance(callback.message, Message):
            await _ask_pdf(callback.message, state)

    @router.message(Command("template"))
    async def template_command(message: Message) -> None:
        await message.answer(empty_template_text())

    @router.message(Command("my_template"))
    async def my_template(message: Message) -> None:
        user_id = _message_user_id(message)
        if user_id is None:
            await message.answer("Не удалось определить Telegram ID пользователя.")
            return
        data = context.storage.get_user_template(user_id)
        if data is None:
            await message.answer("Сохранённый шаблон пока отсутствует.")
            return
        await message.answer(template_to_user_text(data))

    @router.message(Command("delete_template"))
    async def delete_template(message: Message) -> None:
        user_id = _message_user_id(message)
        if user_id is None:
            await message.answer("Не удалось определить Telegram ID пользователя.")
            return
        deleted = context.storage.delete_user_template(user_id)
        await message.answer("Шаблон удалён." if deleted else "Сохранённый шаблон не найден.")

    @router.message(Command("cancel"))
    async def cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Операция отменена.")

    @router.message(TtnStates.waiting_pdf, F.document)
    async def receive_pdf(message: Message, state: FSMContext, bot: Bot) -> None:
        document = message.document
        if document is None:
            return
        user_id = _message_user_id(message)
        if user_id is None:
            await message.answer("Не удалось определить Telegram ID пользователя.")
            return
        if not document.file_name or not document.file_name.lower().endswith(".pdf"):
            await message.answer("Загрузите документ в формате PDF.")
            return
        if document.mime_type not in {"application/pdf", "application/x-pdf"}:
            await message.answer("Файл должен иметь MIME-тип PDF.")
            return
        if document.file_size and document.file_size > context.settings.max_file_size_bytes:
            await message.answer(f"Размер PDF превышает {context.settings.max_file_size_mb} МБ.")
            return

        job_id = uuid.uuid4().hex
        job_dir = context.settings.temp_dir / str(user_id) / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        source_path = job_dir / _safe_pdf_file_name(document.file_name)
        file = await bot.get_file(document.file_id)
        if file.file_path is None:
            await message.answer(
                "Не удалось получить файл из Telegram. Попробуйте загрузить PDF ещё раз."
            )
            return
        await bot.download_file(file.file_path, destination=source_path)

        try:
            validate_pdf(source_path, context.template)
        except PdfValidationError as exc:
            shutil.rmtree(job_dir, ignore_errors=True)
            await message.answer(exc.user_message)
            return

        context.storage.create_job(job_id, user_id, source_path)
        await state.set_state(TtnStates.waiting_full_data)
        await state.update_data(job_id=job_id, job_dir=str(job_dir), source_pdf=str(source_path))
        await message.answer(
            "PDF проверен. Заполните данные одним сообщением:\n\n" + empty_template_text(),
            reply_markup=fill_mode_keyboard(),
        )

    @router.message(TtnStates.waiting_pdf)
    async def receive_non_pdf(message: Message) -> None:
        await message.answer("Загрузите исходную ТТН как документ PDF.")

    @router.callback_query(TtnStates.waiting_full_data, F.data == "step_fill")
    async def step_fill(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        await state.set_state(TtnStates.waiting_step_value)
        await state.update_data(step_index=0, step_values={})
        if isinstance(callback.message, Message):
            await callback.message.answer(STEP_FIELDS[0][1])

    @router.message(TtnStates.waiting_step_value)
    async def receive_step_value(message: Message, state: FSMContext) -> None:
        state_data = await state.get_data()
        step_index = int(state_data.get("step_index", 0))
        step_values = dict(state_data.get("step_values", {}))
        field_name = STEP_FIELDS[step_index][0]
        step_values[field_name] = message.text or ""
        step_index += 1
        if step_index < len(STEP_FIELDS):
            await state.update_data(step_index=step_index, step_values=step_values)
            await message.answer(STEP_FIELDS[step_index][1])
            return
        try:
            edit_data = _edit_data_from_steps(step_values)
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await _finish_job(message, state, edit_data, context)

    @router.message(TtnStates.waiting_full_data, F.text)
    async def receive_full_data(message: Message, state: FSMContext) -> None:
        try:
            edit_data = parse_edit_data_message(message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await _finish_job(message, state, edit_data, context)

    @router.message()
    async def fallback(message: Message) -> None:
        await message.answer(
            "Используйте /new, чтобы обработать новую ТТН, или /help для инструкции."
        )

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


async def _ask_pdf(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(TtnStates.waiting_pdf)
    await message.answer("Загрузите исходную ТТН как документ PDF.")


async def _finish_job(
    message: Message,
    state: FSMContext,
    edit_data: TtnEditData,
    context: BotContext,
) -> None:
    state_data = await state.get_data()
    job_id = str(state_data["job_id"])
    job_dir = Path(str(state_data["job_dir"]))
    source_pdf = Path(str(state_data["source_pdf"]))

    await message.answer("Заполняю PDF и создаю Excel. Это может занять несколько секунд.")
    async with context.semaphore:
        try:
            result = await asyncio.to_thread(
                process_ttn_job,
                job_id,
                job_dir,
                source_pdf,
                edit_data,
                context.template,
                context.settings.font_path,
                context.storage,
            )
        except Exception as exc:
            logger.exception("TTN job failed")
            context.storage.update_job(job_id, "failed", str(exc))
            await message.answer("Не удалось обработать ТТН. Проверьте PDF или шаблон документа.")
            return

    user_id = _message_user_id(message)
    if user_id is not None:
        context.storage.save_user_template(user_id, edit_data)
    await state.clear()
    await message.answer_document(FSInputFile(result.filled_pdf))
    await message.answer_document(FSInputFile(result.excel))
    await message.answer("Готово. Данные сохранены как ваш шаблон для следующих ТТН.")


def _edit_data_from_steps(values: dict[str, str]) -> TtnEditData:
    series, number = parse_series_and_number(values.pop("series_and_number", ""))
    driver = values.get("driver", "")
    release_allowed_by = values.get("release_allowed_by", "")
    return TtnEditData(
        vehicle=values.get("vehicle", ""),
        driver=driver,
        ttn_series=series,
        ttn_number=number,
        goods_accepted_by=driver,
        release_allowed_by=release_allowed_by,
        shipper_handed_over_by=release_allowed_by,
    )


def _is_allowed(user_id: int, allowed_user_ids: list[int]) -> bool:
    return not allowed_user_ids or user_id in allowed_user_ids


def _open_downloads_folder() -> None:
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        return
    startfile = getattr(os, "startfile", None)
    if callable(startfile):
        startfile(downloads)


def _safe_pdf_file_name(file_name: str) -> str:
    safe_name = Path(file_name).name.strip()
    if not safe_name or safe_name in {".", ".."}:
        return "source.pdf"
    return safe_name


def _message_user_id(message: Message | InaccessibleMessage) -> int | None:
    if not isinstance(message, Message) or message.from_user is None:
        return None
    return message.from_user.id
