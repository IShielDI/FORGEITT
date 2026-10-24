"""initial schema: core tables from TRD section 3 (SQLite)

Revision ID: 0001
Revises:
Create Date: 2026-10-24 15:57:17.653456
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "succeeded",
                "failed",
                name="job_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_jobs_attempts_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.create_index("ix_jobs_status_created_at", ["status", "created_at"], unique=False)

    op.create_table(
        "users",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "workspaces",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column(
            "verification_profile",
            sa.Enum(
                "fast",
                "standard",
                "strict",
                name="verification_profile",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="fast",
            nullable=False,
        ),
        sa.Column("allowed_providers", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_workspaces_owner_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
    )
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_workspaces_owner_id"), ["owner_id"], unique=False)

    op.create_table(
        "contracts",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "api",
                "schema",
                "type",
                name="contract_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "proposed",
                "approved",
                "rejected",
                "superseded",
                name="contract_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="proposed",
            nullable=False,
        ),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_contracts_version_positive")),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_contracts_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contracts")),
        sa.UniqueConstraint(
            "workspace_id", "name", "version", name=op.f("uq_contracts_workspace_id_name_version")
        ),
    )
    with op.batch_alter_table("contracts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_contracts_workspace_id"), ["workspace_id"], unique=False
        )

    op.create_table(
        "hidden_tests",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.String(length=36), nullable=False),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("location", sa.String(length=1024), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "approved",
                "retired",
                name="hidden_test_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["users.id"],
            name=op.f("fk_hidden_tests_approved_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_hidden_tests_author_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_hidden_tests_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hidden_tests")),
    )
    with op.batch_alter_table("hidden_tests", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_hidden_tests_approved_by"), ["approved_by"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_hidden_tests_author_id"), ["author_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_hidden_tests_workspace_id"), ["workspace_id"], unique=False
        )

    op.create_table(
        "integration_runs",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_branch", sa.String(length=255), nullable=False),
        sa.Column("base_sha", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "passed",
                "failed",
                "error",
                "cancelled",
                name="run_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="queued",
            nullable=False,
        ),
        sa.Column(
            "profile",
            sa.Enum(
                "fast",
                "standard",
                "strict",
                name="verification_profile",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_integration_runs_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_runs")),
    )
    with op.batch_alter_table("integration_runs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_integration_runs_workspace_id"), ["workspace_id"], unique=False
        )

    op.create_table(
        "invites",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "owner",
                "member",
                "viewer",
                name="member_role",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="member",
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(used_at IS NULL) = (used_by IS NULL)", name=op.f("ck_invites_used_at_and_by_together")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_invites_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["used_by"], ["users.id"], name=op.f("fk_invites_used_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_invites_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invites")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invites_token_hash")),
    )
    with op.batch_alter_table("invites", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_invites_created_by"), ["created_by"], unique=False)
        batch_op.create_index(batch_op.f("ix_invites_used_by"), ["used_by"], unique=False)
        batch_op.create_index(batch_op.f("ix_invites_workspace_id"), ["workspace_id"], unique=False)

    op.create_table(
        "knowledge_links",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column(
            "src_type",
            sa.Enum(
                "requirement",
                "decision",
                "contract",
                "task",
                "submission",
                "commit",
                "check_result",
                "failure",
                name="src_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("src_id", sa.String(length=36), nullable=False),
        sa.Column(
            "dst_type",
            sa.Enum(
                "requirement",
                "decision",
                "contract",
                "task",
                "submission",
                "commit",
                "check_result",
                "failure",
                name="dst_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("dst_id", sa.String(length=36), nullable=False),
        sa.Column("relation", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_knowledge_links_version_positive")),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_knowledge_links_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_links")),
    )
    with op.batch_alter_table("knowledge_links", schema=None) as batch_op:
        batch_op.create_index("ix_knowledge_links_dst", ["dst_type", "dst_id"], unique=False)
        batch_op.create_index("ix_knowledge_links_src", ["src_type", "src_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_knowledge_links_workspace_id"), ["workspace_id"], unique=False
        )

    op.create_table(
        "members",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "owner",
                "member",
                "viewer",
                name="member_role",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="member",
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_members_user_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_members_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_members")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_members_token_hash")),
        sa.UniqueConstraint(
            "workspace_id", "user_id", name=op.f("uq_members_workspace_id_user_id")
        ),
    )
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_members_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_members_workspace_id"), ["workspace_id"], unique=False)

    op.create_table(
        "messages",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_messages_user_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_messages_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_messages_user_id"), ["user_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_messages_workspace_id"), ["workspace_id"], unique=False
        )
        batch_op.create_index(
            "ix_messages_workspace_id_created_at", ["workspace_id", "created_at"], unique=False
        )

    op.create_table(
        "spec_items",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "requirement",
                "decision",
                "suggestion",
                "question",
                name="spec_item_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "proposed",
                "confirmed",
                "rejected",
                name="spec_item_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="proposed",
            nullable=False,
        ),
        sa.Column("source_message_ids", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("confirmed_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_spec_items_version_positive")),
        sa.ForeignKeyConstraint(
            ["confirmed_by"],
            ["users.id"],
            name=op.f("fk_spec_items_confirmed_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_spec_items_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_spec_items_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spec_items")),
    )
    with op.batch_alter_table("spec_items", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_spec_items_workspace_id"), ["workspace_id"], unique=False
        )

    op.create_table(
        "spec_versions",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_spec_versions_version_positive")),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_spec_versions_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spec_versions")),
        sa.UniqueConstraint(
            "workspace_id", "version", name=op.f("uq_spec_versions_workspace_id_version")
        ),
    )
    with op.batch_alter_table("spec_versions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_spec_versions_workspace_id"), ["workspace_id"], unique=False
        )

    op.create_table(
        "tasks",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("component", sa.String(length=200), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "proposed",
                "ready",
                "in_progress",
                "submitted",
                "failed",
                "done",
                name="task_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="proposed",
            nullable=False,
        ),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column("depends_on", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("contract_ids", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_tasks_owner_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_tasks_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_tasks_owner_id"), ["owner_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_tasks_workspace_id"), ["workspace_id"], unique=False)

    op.create_table(
        "approvals",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("approver_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_sha", sa.String(length=64), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "approved",
                "rejected",
                name="approval_decision",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("merged_sha", sa.String(length=64), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "merged_sha IS NULL OR decision = 'approved'",
            name=op.f("ck_approvals_merged_only_if_approved"),
        ),
        sa.ForeignKeyConstraint(
            ["approver_id"],
            ["users.id"],
            name=op.f("fk_approvals_approver_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["integration_runs.id"],
            name=op.f("fk_approvals_run_id_integration_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approvals")),
    )
    with op.batch_alter_table("approvals", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_approvals_approver_id"), ["approver_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_approvals_run_id"), ["run_id"], unique=False)

    op.create_table(
        "check_results",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "merge",
                "build",
                "locked_test",
                "hidden_test",
                "lint",
                "contract",
                "dependency_scan",
                "secret_scan",
                name="check_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "passed",
                "failed",
                "error",
                "skipped",
                name="check_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("log_path", sa.String(length=1024), nullable=True),
        sa.Column("artifacts_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["integration_runs.id"],
            name=op.f("fk_check_results_run_id_integration_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_check_results")),
    )
    with op.batch_alter_table("check_results", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_check_results_run_id"), ["run_id"], unique=False)

    op.create_table(
        "credit_ledger",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "portion",
                "usage",
                "loan",
                "house",
                name="credit_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("amount_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_credit_ledger_task_id_tasks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_credit_ledger_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_credit_ledger_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_ledger")),
    )
    with op.batch_alter_table("credit_ledger", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_credit_ledger_task_id"), ["task_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_credit_ledger_user_id"), ["user_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_credit_ledger_workspace_id"), ["workspace_id"], unique=False
        )
        batch_op.create_index(
            "ix_credit_ledger_workspace_id_user_id", ["workspace_id", "user_id"], unique=False
        )

    op.create_table(
        "referee_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "verdict",
            sa.Enum(
                "pass",
                "app_failure",
                "browser_failure",
                "service_error",
                "inconclusive",
                "not_run",
                name="referee_verdict",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="not_run",
            nullable=False,
        ),
        sa.Column("evidence_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["integration_runs.id"],
            name=op.f("fk_referee_runs_run_id_integration_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_referee_runs")),
    )
    with op.batch_alter_table("referee_runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_referee_runs_run_id"), ["run_id"], unique=False)

    op.create_table(
        "submissions",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("handoff_summary", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "accepted",
                "rejected",
                "superseded",
                name="submission_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_submissions_task_id_tasks"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
    )
    with op.batch_alter_table("submissions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_submissions_task_id"), ["task_id"], unique=False)

    op.create_table(
        "failures",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("check_result_id", sa.String(length=36), nullable=True),
        sa.Column("suspected_task_id", sa.String(length=36), nullable=True),
        sa.Column("suspected_contract_id", sa.String(length=36), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "routed",
                "resolved",
                "dismissed",
                name="failure_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="open",
            nullable=False,
        ),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_failures_confidence_range")
        ),
        sa.ForeignKeyConstraint(
            ["check_result_id"],
            ["check_results.id"],
            name=op.f("fk_failures_check_result_id_check_results"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["integration_runs.id"],
            name=op.f("fk_failures_run_id_integration_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["suspected_contract_id"],
            ["contracts.id"],
            name=op.f("fk_failures_suspected_contract_id_contracts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["suspected_task_id"],
            ["tasks.id"],
            name=op.f("fk_failures_suspected_task_id_tasks"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_failures")),
    )
    with op.batch_alter_table("failures", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_failures_check_result_id"), ["check_result_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_failures_run_id"), ["run_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_failures_suspected_contract_id"), ["suspected_contract_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_failures_suspected_task_id"), ["suspected_task_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("failures", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_failures_suspected_task_id"))
        batch_op.drop_index(batch_op.f("ix_failures_suspected_contract_id"))
        batch_op.drop_index(batch_op.f("ix_failures_run_id"))
        batch_op.drop_index(batch_op.f("ix_failures_check_result_id"))

    op.drop_table("failures")
    with op.batch_alter_table("submissions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_submissions_task_id"))

    op.drop_table("submissions")
    with op.batch_alter_table("referee_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_referee_runs_run_id"))

    op.drop_table("referee_runs")
    with op.batch_alter_table("credit_ledger", schema=None) as batch_op:
        batch_op.drop_index("ix_credit_ledger_workspace_id_user_id")
        batch_op.drop_index(batch_op.f("ix_credit_ledger_workspace_id"))
        batch_op.drop_index(batch_op.f("ix_credit_ledger_user_id"))
        batch_op.drop_index(batch_op.f("ix_credit_ledger_task_id"))

    op.drop_table("credit_ledger")
    with op.batch_alter_table("check_results", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_check_results_run_id"))

    op.drop_table("check_results")
    with op.batch_alter_table("approvals", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_approvals_run_id"))
        batch_op.drop_index(batch_op.f("ix_approvals_approver_id"))

    op.drop_table("approvals")
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tasks_workspace_id"))
        batch_op.drop_index(batch_op.f("ix_tasks_owner_id"))

    op.drop_table("tasks")
    with op.batch_alter_table("spec_versions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_spec_versions_workspace_id"))

    op.drop_table("spec_versions")
    with op.batch_alter_table("spec_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_spec_items_workspace_id"))

    op.drop_table("spec_items")
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.drop_index("ix_messages_workspace_id_created_at")
        batch_op.drop_index(batch_op.f("ix_messages_workspace_id"))
        batch_op.drop_index(batch_op.f("ix_messages_user_id"))

    op.drop_table("messages")
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_members_workspace_id"))
        batch_op.drop_index(batch_op.f("ix_members_user_id"))

    op.drop_table("members")
    with op.batch_alter_table("knowledge_links", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_knowledge_links_workspace_id"))
        batch_op.drop_index("ix_knowledge_links_src")
        batch_op.drop_index("ix_knowledge_links_dst")

    op.drop_table("knowledge_links")
    with op.batch_alter_table("invites", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_invites_workspace_id"))
        batch_op.drop_index(batch_op.f("ix_invites_used_by"))
        batch_op.drop_index(batch_op.f("ix_invites_created_by"))

    op.drop_table("invites")
    with op.batch_alter_table("integration_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_integration_runs_workspace_id"))

    op.drop_table("integration_runs")
    with op.batch_alter_table("hidden_tests", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_hidden_tests_workspace_id"))
        batch_op.drop_index(batch_op.f("ix_hidden_tests_author_id"))
        batch_op.drop_index(batch_op.f("ix_hidden_tests_approved_by"))

    op.drop_table("hidden_tests")
    with op.batch_alter_table("contracts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_contracts_workspace_id"))

    op.drop_table("contracts")
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_workspaces_owner_id"))

    op.drop_table("workspaces")
    op.drop_table("users")
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_index("ix_jobs_status_created_at")

    op.drop_table("jobs")
