"""Add Ozon reviews workflow."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "0004_ozon_reviews"
down_revision = "0003_question_bigint_ids"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ozon_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("client_id", sa.String(128), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "ozon_review_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auto_send", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "ozon_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ozon_review_id", sa.String(128), nullable=False),
        sa.Column(
            "ozon_account_id",
            sa.Integer(),
            sa.ForeignKey("ozon_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sku", sa.BigInteger()),
        sa.Column("product_id", sa.BigInteger()),
        sa.Column("offer_id", sa.String(255)),
        sa.Column("product_name", sa.String(500)),
        sa.Column("buyer_name", sa.String(255)),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("review_text", sa.Text()),
        sa.Column("pros", sa.Text()),
        sa.Column("cons", sa.Text()),
        sa.Column("published_at_ozon", sa.DateTime(timezone=True)),
        sa.Column("ozon_status", sa.String(64)),
        sa.Column("has_official_comment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("answer_text", sa.Text()),
        sa.Column("answer_sent_at", sa.DateTime(timezone=True)),
        sa.Column("selected_template_id", sa.Integer(), sa.ForeignKey("ozon_review_templates.id")),
        sa.Column("edited_by_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("postponed_until", sa.DateTime(timezone=True)),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ozon_review_rating_range"),
        sa.UniqueConstraint("ozon_account_id", "ozon_review_id"),
    )
    op.create_table(
        "ozon_review_template_keywords",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("ozon_review_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(255), nullable=False),
        sa.Column("normalized_keyword", sa.String(255), nullable=False),
        sa.UniqueConstraint("template_id", "normalized_keyword"),
    )
    op.create_table(
        "ozon_review_template_ratings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("ozon_review_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.UniqueConstraint("template_id", "rating"),
    )
    op.create_table(
        "ozon_review_template_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("ozon_review_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("offer_id", sa.String(255), nullable=False),
        sa.UniqueConstraint("template_id", "offer_id"),
    )
    op.create_table(
        "ozon_review_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "review_id",
            sa.Integer(),
            sa.ForeignKey("ozon_reviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("telegram_user_id", sa.BigInteger()),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("old_status", sa.String(32)),
        sa.Column("new_status", sa.String(32)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ozon_review_actions")
    op.drop_table("ozon_review_template_products")
    op.drop_table("ozon_review_template_ratings")
    op.drop_table("ozon_review_template_keywords")
    op.drop_table("ozon_reviews")
    op.drop_table("ozon_review_templates")
    op.drop_table("ozon_accounts")
