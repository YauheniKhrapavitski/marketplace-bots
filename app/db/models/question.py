from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Question(TimestampMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("wb_account_id", "wb_question_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    wb_question_id: Mapped[str] = mapped_column(String(128), index=True)
    wb_account_id: Mapped[int] = mapped_column(ForeignKey("wb_accounts.id", ondelete="CASCADE"))
    nm_id: Mapped[int | None] = mapped_column(BigInteger)
    imt_id: Mapped[int | None] = mapped_column(BigInteger)
    product_name: Mapped[str | None] = mapped_column(String(500))
    supplier_article: Mapped[str | None] = mapped_column(String(255))
    brand_name: Mapped[str | None] = mapped_column(String(255))
    question_text: Mapped[str] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(String(64))
    created_at_wb: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    was_viewed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_warned: Mapped[bool] = mapped_column(Boolean, default=False)
    answer_text: Mapped[str | None] = mapped_column(Text)
    answer_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selected_template_id: Mapped[int | None] = mapped_column(ForeignKey("question_templates.id"))
    edited_by_user: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class QuestionTemplate(TimestampMixin, Base):
    __tablename__ = "question_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(50), index=True)
    text: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    auto_send: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class QuestionTemplateKeyword(Base):
    __tablename__ = "question_template_keywords"
    __table_args__ = (UniqueConstraint("template_id", "normalized_keyword"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("question_templates.id", ondelete="CASCADE")
    )
    keyword: Mapped[str] = mapped_column(String(255))
    normalized_keyword: Mapped[str] = mapped_column(String(255), index=True)


class QuestionTemplateProduct(Base):
    __tablename__ = "question_template_products"
    __table_args__ = (UniqueConstraint("template_id", "nm_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("question_templates.id", ondelete="CASCADE")
    )
    nm_id: Mapped[int] = mapped_column(BigInteger, index=True)


class QuestionAction(TimestampMixin, Base):
    __tablename__ = "question_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(50), index=True)
    old_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str | None] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
