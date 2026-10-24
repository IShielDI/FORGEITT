"""hidden test authoring: drafts approved by a second person (stage 22)

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-24 18:26:54.100135
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hidden_tests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=True),
        sa.Column("created", sa.Float(), nullable=True),
        sa.Column("approved_at", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hidden_tests")),
        sa.UniqueConstraint("room_id", "filename", name=op.f("uq_hidden_tests_room_id_filename")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("hidden_tests", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_hidden_tests_room_id"), ["room_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("hidden_tests", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_hidden_tests_room_id"))

    op.drop_table("hidden_tests")
