"""spec items and versions, observer cursor (stages 7-8)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-24 18:01:35.452292
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spec_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'proposed'"), nullable=True),
        sa.Column("source_message_ids", sa.Text(), server_default=sa.text("'[]'"), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=True),
        sa.Column("supersedes_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("created", sa.Float(), nullable=True),
        sa.Column("decided", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spec_items")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("spec_items", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_spec_items_room_id"), ["room_id"], unique=False)

    op.create_table(
        "spec_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("snapshot", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spec_versions")),
        sa.UniqueConstraint("room_id", "version", name=op.f("uq_spec_versions_room_id_version")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("spec_versions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_spec_versions_room_id"), ["room_id"], unique=False)

    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("observer_cursor", sa.Integer(), server_default=sa.text("0"), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.drop_column("observer_cursor")

    with op.batch_alter_table("spec_versions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_spec_versions_room_id"))

    op.drop_table("spec_versions")
    with op.batch_alter_table("spec_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_spec_items_room_id"))

    op.drop_table("spec_items")
