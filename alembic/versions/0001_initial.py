"""Initial schema and starter templates."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.String(255)),
        sa.Column("first_name", sa.String(255)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "wb_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("encrypted_api_token", sa.Text(), nullable=False),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "feedbacks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("wb_feedback_id", sa.String(128), nullable=False),
        sa.Column(
            "wb_account_id",
            sa.Integer(),
            sa.ForeignKey("wb_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nm_id", sa.Integer()),
        sa.Column("product_name", sa.String(500)),
        sa.Column("supplier_article", sa.String(255)),
        sa.Column("buyer_name", sa.String(255)),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("review_text", sa.Text()),
        sa.Column("pros", sa.Text()),
        sa.Column("cons", sa.Text()),
        sa.Column("created_at_wb", sa.DateTime(timezone=True)),
        sa.Column("answer_text", sa.Text()),
        sa.Column("answer_sent_at", sa.DateTime(timezone=True)),
        sa.Column("selected_template_id", sa.Integer(), sa.ForeignKey("templates.id")),
        sa.Column("edited_by_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("notification_sent_at", sa.DateTime(timezone=True)),
        sa.Column("postponed_until", sa.DateTime(timezone=True)),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="feedback_rating_range"),
        sa.UniqueConstraint("wb_account_id", "wb_feedback_id"),
    )
    op.create_table(
        "template_ratings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.UniqueConstraint("template_id", "rating"),
    )
    op.create_table(
        "template_keywords",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(255), nullable=False),
        sa.Column("normalized_keyword", sa.String(255), nullable=False),
        sa.UniqueConstraint("template_id", "normalized_keyword"),
    )
    op.create_table(
        "template_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nm_id", sa.Integer(), nullable=False),
        sa.UniqueConstraint("template_id", "nm_id"),
    )
    op.create_table(
        "feedback_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "feedback_id",
            sa.Integer(),
            sa.ForeignKey("feedbacks.id", ondelete="CASCADE"),
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
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("received_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("sync_runs")
    op.drop_table("feedback_actions")
    op.drop_table("template_products")
    op.drop_table("template_keywords")
    op.drop_table("template_ratings")
    op.drop_table("feedbacks")
    op.drop_table("templates")
    op.drop_table("wb_accounts")
    op.drop_table("users")
