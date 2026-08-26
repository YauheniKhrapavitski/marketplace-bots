"""Use bigint for buyer question product identifiers."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "0003_question_bigint_ids"
down_revision = "0002_buyer_questions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("questions", "nm_id", existing_type=sa.Integer(), type_=sa.BigInteger())
    op.alter_column("questions", "imt_id", existing_type=sa.Integer(), type_=sa.BigInteger())
    op.alter_column(
        "question_template_products", "nm_id", existing_type=sa.Integer(), type_=sa.BigInteger()
    )


def downgrade() -> None:
    op.alter_column(
        "question_template_products", "nm_id", existing_type=sa.BigInteger(), type_=sa.Integer()
    )
    op.alter_column("questions", "imt_id", existing_type=sa.BigInteger(), type_=sa.Integer())
    op.alter_column("questions", "nm_id", existing_type=sa.BigInteger(), type_=sa.Integer())
