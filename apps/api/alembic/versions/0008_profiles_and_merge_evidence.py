"""room verification profile; merges record candidate sha, merged sha, release tag (18-19)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-24 18:17:56.680420
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("merges", schema=None) as batch_op:
        batch_op.add_column(sa.Column("candidate_sha", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("merged_sha", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("release_tag", sa.Text(), nullable=True))

    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("verification_profile", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.drop_column("verification_profile")

    with op.batch_alter_table("merges", schema=None) as batch_op:
        batch_op.drop_column("release_tag")
        batch_op.drop_column("merged_sha")
        batch_op.drop_column("candidate_sha")
