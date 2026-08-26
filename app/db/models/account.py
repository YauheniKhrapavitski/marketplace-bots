from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WbAccount(TimestampMixin, Base):
    __tablename__ = "wb_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="Default")
    encrypted_api_token: Mapped[str] = mapped_column(Text)
    environment: Mapped[str] = mapped_column(String(32), default="sandbox")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_error: Mapped[str | None] = mapped_column(Text)
