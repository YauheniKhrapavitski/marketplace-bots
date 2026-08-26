from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Feedback(TimestampMixin, Base):
    __tablename__ = "feedbacks"
    __table_args__ = (
        UniqueConstraint("wb_account_id", "wb_feedback_id"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="feedback_rating_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wb_feedback_id: Mapped[str] = mapped_column(String(128), index=True)
    wb_account_id: Mapped[int] = mapped_column(ForeignKey("wb_accounts.id", ondelete="CASCADE"))
    nm_id: Mapped[int | None] = mapped_column(Integer)
    product_name: Mapped[str | None] = mapped_column(String(500))
    supplier_article: Mapped[str | None] = mapped_column(String(255))
    buyer_name: Mapped[str | None] = mapped_column(String(255))
    rating: Mapped[int] = mapped_column(Integer)
    review_text: Mapped[str | None] = mapped_column(Text)
    pros: Mapped[str | None] = mapped_column(Text)
    cons: Mapped[str | None] = mapped_column(Text)
    created_at_wb: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answer_text: Mapped[str | None] = mapped_column(Text)
    answer_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selected_template_id: Mapped[int | None] = mapped_column(ForeignKey("templates.id"))
    edited_by_user: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    notification_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    postponed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
