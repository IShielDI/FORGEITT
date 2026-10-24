"""allowed providers per workspace, and free prices for local providers (stage 6)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-24 17:58:22.764632
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("allowed_providers", sa.Text(), nullable=True))

    # mock (tests/dev) costs nothing; the ledger still records every call
    op.execute("INSERT OR IGNORE INTO prices VALUES('mock', 0, 0, 0, 0)")


def downgrade() -> None:
    op.execute("DELETE FROM prices WHERE model='mock'")
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.drop_column("allowed_providers")
