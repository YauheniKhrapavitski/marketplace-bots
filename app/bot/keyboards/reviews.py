from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def review_keyboard(feedback_id: int, product_url: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Отправить ответ", callback_data=f"review:send:{feedback_id}")],
        [
            InlineKeyboardButton(text="Редактировать", callback_data=f"review:edit:{feedback_id}"),
            InlineKeyboardButton(
                text="Другой шаблон", callback_data=f"review:template:{feedback_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="Свой вариант ответа", callback_data=f"review:custom:{feedback_id}"
            )
        ],
        [
            InlineKeyboardButton(text="Пропустить", callback_data=f"review:skip:{feedback_id}"),
            InlineKeyboardButton(text="Следующий отзыв", callback_data="review:next"),
        ],
    ]
    if product_url:
        rows.append([InlineKeyboardButton(text="Карточка товара", url=product_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def skip_keyboard(feedback_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Вернуться позже", callback_data=f"review:postpone:{feedback_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Не отвечать", callback_data=f"review:ignore:{feedback_id}"
                )
            ],
            [InlineKeyboardButton(text="Отмена", callback_data=f"review:cancel:{feedback_id}")],
        ]
    )
