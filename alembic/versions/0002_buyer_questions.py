"""Add buyer questions workflow."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "0002_buyer_questions"
down_revision = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auto_send", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("wb_question_id", sa.String(128), nullable=False),
        sa.Column(
            "wb_account_id",
            sa.Integer(),
            sa.ForeignKey("wb_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nm_id", sa.Integer()),
        sa.Column("imt_id", sa.Integer()),
        sa.Column("product_name", sa.String(500)),
        sa.Column("supplier_article", sa.String(255)),
        sa.Column("brand_name", sa.String(255)),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("state", sa.String(64)),
        sa.Column("created_at_wb", sa.DateTime(timezone=True)),
        sa.Column("was_viewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_warned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("answer_text", sa.Text()),
        sa.Column("answer_sent_at", sa.DateTime(timezone=True)),
        sa.Column("selected_template_id", sa.Integer(), sa.ForeignKey("question_templates.id")),
        sa.Column("edited_by_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("wb_account_id", "wb_question_id"),
    )
    op.create_table(
        "question_template_keywords",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("question_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(255), nullable=False),
        sa.Column("normalized_keyword", sa.String(255), nullable=False),
        sa.UniqueConstraint("template_id", "normalized_keyword"),
    )
    op.create_table(
        "question_template_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("question_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nm_id", sa.Integer(), nullable=False),
        sa.UniqueConstraint("template_id", "nm_id"),
    )
    op.create_table(
        "question_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
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
    op.drop_table("question_actions")
    op.drop_table("question_template_products")
    op.drop_table("question_template_keywords")
    op.drop_table("questions")
    op.drop_table("question_templates")
