from html import escape

from app.db.models.feedback import Feedback


def format_feedback_card(feedback: Feedback) -> str:
    lines = ["<b>Новый отзыв</b>", ""]
    add(lines, "Товар", feedback.product_name)
    add(lines, "Артикул WB", str(feedback.nm_id) if feedback.nm_id else None)
    add(lines, "Оценка", f"{feedback.rating} из 5")
    add(lines, "Покупатель", feedback.buyer_name)
    add(lines, "Дата", feedback.created_at_wb.isoformat() if feedback.created_at_wb else None)
    block(lines, "Отзыв", feedback.review_text)
    block(lines, "Достоинства", feedback.pros)
    block(lines, "Недостатки", feedback.cons)
    block(lines, "Предлагаемый ответ", feedback.answer_text)
    return "\n".join(lines)


def add(lines: list[str], label: str, value: str | None) -> None:
    if value:
        lines.append(f"<b>{escape(label)}:</b> {escape(value)}")


def block(lines: list[str], label: str, value: str | None) -> None:
    if value:
        lines.extend(["", f"<b>{escape(label)}:</b>", escape(value)])
