"""spec conflicts: contradicting spec items and the picks people make to settle them

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-25 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spec_conflicts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("item_a", sa.Integer(), nullable=True),
        sa.Column("item_b", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'open'"), nullable=True),
        sa.Column("winner_id", sa.Integer(), nullable=True),
        sa.Column("decided_how", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("created", sa.Float(), nullable=True),
        sa.Column("decided", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spec_conflicts")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("spec_conflicts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_spec_conflicts_room_id"), ["room_id"], unique=False)

    op.create_table(
        "conflict_votes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("conflict_id", sa.Integer(), nullable=True),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("choice", sa.Integer(), nullable=True),
        sa.Column("created", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conflict_votes")),
        sa.UniqueConstraint(
            "conflict_id", "member_id", name=op.f("uq_conflict_votes_conflict_id_member_id")
        ),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("conflict_votes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_conflict_votes_room_id"), ["room_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_conflict_votes_conflict_id"), ["conflict_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("conflict_votes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_conflict_votes_conflict_id"))
        batch_op.drop_index(batch_op.f("ix_conflict_votes_room_id"))
    op.drop_table("conflict_votes")
    with op.batch_alter_table("spec_conflicts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_spec_conflicts_room_id"))
    op.drop_table("spec_conflicts")
