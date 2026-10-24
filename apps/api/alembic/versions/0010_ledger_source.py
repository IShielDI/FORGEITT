"""ledger rows record who pays: own portion, loan or capped house key (stage 25)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-24 18:34:54.397579
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ledger", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.Text(), server_default=sa.text("'own'"), nullable=True)
        )

    op.execute("UPDATE ledger SET source='loan' WHERE loan_id IS NOT NULL")


def downgrade() -> None:
    with op.batch_alter_table("ledger", schema=None) as batch_op:
        batch_op.drop_column("source")
