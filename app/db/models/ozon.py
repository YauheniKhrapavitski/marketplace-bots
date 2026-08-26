from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
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


class OzonAccount(TimestampMixin, Base):
    __tablename__ = "ozon_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="Default")
    client_id: Mapped[str] = mapped_column(String(128))
    encrypted_api_key: Mapped[str] = mapped_column(Text)
    environment: Mapped[str] = mapped_column(String(32), default="production")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_error: Mapped[str | None] = mapped_column(Text)


class OzonReview(TimestampMixin, Base):
    __tablename__ = "ozon_reviews"
    __table_args__ = (
        UniqueConstraint("ozon_account_id", "ozon_review_id"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ozon_review_rating_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ozon_review_id: Mapped[str] = mapped_column(String(128), index=True)
    ozon_account_id: Mapped[int] = mapped_column(
        ForeignKey("ozon_accounts.id", ondelete="CASCADE")
    )
    sku: Mapped[int | None] = mapped_column(BigInteger)
    product_id: Mapped[int | None] = mapped_column(BigInteger)
    offer_id: Mapped[str | None] = mapped_column(String(255))
    product_name: Mapped[str | None] = mapped_column(String(500))
    buyer_name: Mapped[str | None] = mapped_column(String(255))
    rating: Mapped[int] = mapped_column(Integer)
    review_text: Mapped[str | None] = mapped_column(Text)
    pros: Mapped[str | None] = mapped_column(Text)
    cons: Mapped[str | None] = mapped_column(Text)
    published_at_ozon: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ozon_status: Mapped[str | None] = mapped_column(String(64), index=True)
    has_official_comment: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    answer_text: Mapped[str | None] = mapped_column(Text)
    answer_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selected_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("ozon_review_templates.id")
    )
    edited_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    postponed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class OzonReviewTemplate(TimestampMixin, Base):
    __tablename__ = "ozon_review_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(50), index=True)
    text: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    auto_send: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class OzonReviewTemplateKeyword(Base):
    __tablename__ = "ozon_review_template_keywords"
    __table_args__ = (UniqueConstraint("template_id", "normalized_keyword"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("ozon_review_templates.id", ondelete="CASCADE")
    )
    keyword: Mapped[str] = mapped_column(String(255))
    normalized_keyword: Mapped[str] = mapped_column(String(255), index=True)


class OzonReviewTemplateRating(Base):
    __tablename__ = "ozon_review_template_ratings"
    __table_args__ = (UniqueConstraint("template_id", "rating"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("ozon_review_templates.id", ondelete="CASCADE")
    )
    rating: Mapped[int] = mapped_column(Integer, index=True)


class OzonReviewTemplateProduct(Base):
    __tablename__ = "ozon_review_template_products"
    __table_args__ = (UniqueConstraint("template_id", "offer_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("ozon_review_templates.id", ondelete="CASCADE")
    )
    offer_id: Mapped[str] = mapped_column(String(255), index=True)


class OzonReviewAction(TimestampMixin, Base):
    __tablename__ = "ozon_review_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("ozon_reviews.id", ondelete="CASCADE"), index=True
    )
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(50), index=True)
    old_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str | None] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
