"""changes: task link, commit sha, handoff summary, verified sha (stages 13, 14, 18)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-24 18:12:34.720751
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("changes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("task_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("commit_sha", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("handoff", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("verified_sha", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("changes", schema=None) as batch_op:
        batch_op.drop_column("verified_sha")
        batch_op.drop_column("handoff")
        batch_op.drop_column("commit_sha")
        batch_op.drop_column("task_id")
