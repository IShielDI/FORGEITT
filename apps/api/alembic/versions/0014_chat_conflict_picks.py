"""conflict picks can come from a chat reply (the message is remembered)

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-25 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("conflict_votes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_message_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("conflict_votes", schema=None) as batch_op:
        batch_op.drop_column("source_message_id")
