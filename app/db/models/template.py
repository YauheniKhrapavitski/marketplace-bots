from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Template(TimestampMixin, Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(50), index=True)
    text: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    ratings: Mapped[list["TemplateRating"]] = relationship(cascade="all, delete-orphan")
    keywords: Mapped[list["TemplateKeyword"]] = relationship(cascade="all, delete-orphan")
    products: Mapped[list["TemplateProduct"]] = relationship(cascade="all, delete-orphan")


class TemplateRating(Base):
    __tablename__ = "template_ratings"
    __table_args__ = (UniqueConstraint("template_id", "rating"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id", ondelete="CASCADE"))
    rating: Mapped[int] = mapped_column(Integer, index=True)


class TemplateKeyword(Base):
    __tablename__ = "template_keywords"
    __table_args__ = (UniqueConstraint("template_id", "normalized_keyword"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id", ondelete="CASCADE"))
    keyword: Mapped[str] = mapped_column(String(255))
    normalized_keyword: Mapped[str] = mapped_column(String(255), index=True)


class TemplateProduct(Base):
    __tablename__ = "template_products"
    __table_args__ = (UniqueConstraint("template_id", "nm_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id", ondelete="CASCADE"))
    nm_id: Mapped[int] = mapped_column(Integer, index=True)
