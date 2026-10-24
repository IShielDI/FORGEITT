"""tasks, versioned contracts (stage 9) and knowledge links (stage 10)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-24 18:05:49.794597
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contracts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'proposed'"), nullable=True),
        sa.Column("spec_item_ids", sa.Text(), server_default=sa.text("'[]'"), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contracts")),
        sa.UniqueConstraint(
            "room_id", "name", "version", name=op.f("uq_contracts_room_id_name_version")
        ),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("contracts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_contracts_room_id"), ["room_id"], unique=False)

    op.create_table(
        "knowledge_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("src_type", sa.Text(), nullable=True),
        sa.Column("src_id", sa.Text(), nullable=True),
        sa.Column("dst_type", sa.Text(), nullable=True),
        sa.Column("dst_id", sa.Text(), nullable=True),
        sa.Column("relation", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_links")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("knowledge_links", schema=None) as batch_op:
        batch_op.create_index(
            "ix_knowledge_links_dst", ["room_id", "dst_type", "dst_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_knowledge_links_room_id"), ["room_id"], unique=False)
        batch_op.create_index(
            "ix_knowledge_links_src", ["room_id", "src_type", "src_id"], unique=False
        )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("component", sa.Text(), nullable=True),
        sa.Column("depends_on", sa.Text(), server_default=sa.text("'[]'"), nullable=True),
        sa.Column("suggested_owner", sa.Text(), nullable=True),
        sa.Column("owner_member_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'proposed'"), nullable=True),
        sa.Column("spec_item_ids", sa.Text(), server_default=sa.text("'[]'"), nullable=True),
        sa.Column("contract_ids", sa.Text(), server_default=sa.text("'[]'"), nullable=True),
        sa.Column("plan_version", sa.Integer(), server_default=sa.text("1"), nullable=True),
        sa.Column("created", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_tasks_room_id"), ["room_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tasks_room_id"))

    op.drop_table("tasks")
    with op.batch_alter_table("knowledge_links", schema=None) as batch_op:
        batch_op.drop_index("ix_knowledge_links_src")
        batch_op.drop_index(batch_op.f("ix_knowledge_links_room_id"))
        batch_op.drop_index("ix_knowledge_links_dst")

    op.drop_table("knowledge_links")
    with op.batch_alter_table("contracts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_contracts_room_id"))

    op.drop_table("contracts")
