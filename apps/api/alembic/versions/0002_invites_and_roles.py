"""invites and roles: single-use invites, member roles (owner|member|viewer), room slug (stage 3)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24 16:58:11.621611
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("token_hash", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), server_default=sa.text("'member'"), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created", sa.Float(), nullable=True),
        sa.Column("expires", sa.Float(), nullable=True),
        sa.Column("used_at", sa.Float(), nullable=True),
        sa.Column("used_by", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invites")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invites_token_hash")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("invites", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_invites_room_id"), ["room_id"], unique=False)

    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("role", sa.Text(), server_default=sa.text("'member'"), nullable=True)
        )

    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("slug", sa.Text(), nullable=True))

    op.execute("UPDATE members SET role='owner' WHERE is_owner=1")
    op.execute("UPDATE rooms SET slug=lower(replace(name, ' ', '-')) WHERE slug IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.drop_column("slug")

    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.drop_column("role")

    with op.batch_alter_table("invites", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_invites_room_id"))

    op.drop_table("invites")
