"""per-workspace edit scope: limit agent edits to the files relevant to the task

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-24 21:34:37.528311
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("edit_scope", sa.Text(), server_default=sa.text("'off'"), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.drop_column("edit_scope")
