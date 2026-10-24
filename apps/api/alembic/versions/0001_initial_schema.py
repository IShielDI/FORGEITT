"""initial schema: core tables from TRD section 3

Revision ID: 0001
Revises:
Create Date: 2026-10-24 15:31:39.634427
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enum types are created once up front (several are shared between tables)
# and dropped explicitly in downgrade, which autogenerate does not do.
ENUMS: dict[str, postgresql.ENUM] = {
    "job_status": postgresql.ENUM(
        "queued", "running", "succeeded", "failed", name="job_status", create_type=False
    ),
    "verification_profile": postgresql.ENUM(
        "light", "standard", "strict", name="verification_profile", create_type=False
    ),
    "contract_kind": postgresql.ENUM(
        "api", "schema", "type", name="contract_kind", create_type=False
    ),
    "contract_status": postgresql.ENUM(
        "proposed", "approved", "rejected", "superseded", name="contract_status", create_type=False
    ),
    "run_status": postgresql.ENUM(
        "queued",
        "running",
        "passed",
        "failed",
        "error",
        "cancelled",
        name="run_status",
        create_type=False,
    ),
    "entity_type": postgresql.ENUM(
        "requirement",
        "decision",
        "contract",
        "task",
        "submission",
        "commit",
        "check_result",
        "failure",
        name="entity_type",
        create_type=False,
    ),
    "member_role": postgresql.ENUM(
        "owner", "member", "observer", name="member_role", create_type=False
    ),
    "spec_item_kind": postgresql.ENUM(
        "requirement",
        "decision",
        "suggestion",
        "question",
        name="spec_item_kind",
        create_type=False,
    ),
    "spec_item_status": postgresql.ENUM(
        "proposed", "confirmed", "rejected", name="spec_item_status", create_type=False
    ),
    "task_status": postgresql.ENUM(
        "proposed",
        "ready",
        "in_progress",
        "submitted",
        "failed",
        "done",
        name="task_status",
        create_type=False,
    ),
    "approval_decision": postgresql.ENUM(
        "approved", "rejected", name="approval_decision", create_type=False
    ),
    "check_kind": postgresql.ENUM(
        "merge",
        "build",
        "unit_test",
        "lint",
        "typecheck",
        "contract",
        "dependency_scan",
        "secret_scan",
        "browser",
        "hidden_test",
        name="check_kind",
        create_type=False,
    ),
    "check_status": postgresql.ENUM(
        "pending",
        "running",
        "passed",
        "failed",
        "error",
        "skipped",
        name="check_status",
        create_type=False,
    ),
    "submission_status": postgresql.ENUM(
        "pending", "accepted", "rejected", "superseded", name="submission_status", create_type=False
    ),
    "failure_status": postgresql.ENUM(
        "open", "routed", "resolved", "dismissed", name="failure_status", create_type=False
    ),
}


def upgrade() -> None:
    bind = op.get_bind()
    for enum in ENUMS.values():
        enum.create(bind, checkfirst=False)

    op.create_table(
        "jobs",
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", ENUMS["job_status"], server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_jobs_attempts_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index("ix_jobs_status_created_at", "jobs", ["status", "created_at"], unique=False)
    op.create_table(
        "users",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "workspaces",
        sa.Column("room_code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column(
            "verification_profile",
            ENUMS["verification_profile"],
            server_default="light",
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_workspaces_owner_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
        sa.UniqueConstraint("room_code", name=op.f("uq_workspaces_room_code")),
    )
    op.create_index(op.f("ix_workspaces_owner_id"), "workspaces", ["owner_id"], unique=False)
    op.create_table(
        "contracts",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("kind", ENUMS["contract_kind"], nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", ENUMS["contract_status"], server_default="proposed", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
    op.create_index(op.f("ix_contracts_workspace_id"), "contracts", ["workspace_id"], unique=False)
    op.create_table(
        "integration_runs",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("candidate_branch", sa.String(length=255), nullable=False),
        sa.Column("base_sha", sa.String(length=64), nullable=False),
        sa.Column("status", ENUMS["run_status"], server_default="queued", nullable=False),
        sa.Column("profile", ENUMS["verification_profile"], nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
    op.create_index(
        op.f("ix_integration_runs_workspace_id"), "integration_runs", ["workspace_id"], unique=False
    )
    op.create_table(
        "knowledge_links",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("src_type", ENUMS["entity_type"], nullable=False),
        sa.Column("src_id", sa.UUID(), nullable=False),
        sa.Column("dst_type", ENUMS["entity_type"], nullable=False),
        sa.Column("dst_id", sa.UUID(), nullable=False),
        sa.Column("relation", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
    op.create_index(
        "ix_knowledge_links_dst", "knowledge_links", ["dst_type", "dst_id"], unique=False
    )
    op.create_index(
        "ix_knowledge_links_src", "knowledge_links", ["src_type", "src_id"], unique=False
    )
    op.create_index(
        op.f("ix_knowledge_links_workspace_id"), "knowledge_links", ["workspace_id"], unique=False
    )
    op.create_table(
        "members",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", ENUMS["member_role"], server_default="member", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
        sa.UniqueConstraint(
            "workspace_id", "user_id", name=op.f("uq_members_workspace_id_user_id")
        ),
    )
    op.create_index(op.f("ix_members_user_id"), "members", ["user_id"], unique=False)
    op.create_index(op.f("ix_members_workspace_id"), "members", ["workspace_id"], unique=False)
    op.create_table(
        "messages",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
    op.create_index(op.f("ix_messages_user_id"), "messages", ["user_id"], unique=False)
    op.create_index(op.f("ix_messages_workspace_id"), "messages", ["workspace_id"], unique=False)
    op.create_index(
        "ix_messages_workspace_id_created_at",
        "messages",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "spec_items",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("kind", ENUMS["spec_item_kind"], nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", ENUMS["spec_item_status"], server_default="proposed", nullable=False),
        sa.Column(
            "source_message_ids",
            postgresql.ARRAY(sa.UUID()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("confirmed_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
    op.create_index(
        op.f("ix_spec_items_workspace_id"), "spec_items", ["workspace_id"], unique=False
    )
    op.create_table(
        "spec_versions",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
    op.create_index(
        op.f("ix_spec_versions_workspace_id"), "spec_versions", ["workspace_id"], unique=False
    )
    op.create_table(
        "tasks",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("component", sa.String(length=200), nullable=True),
        sa.Column("status", ENUMS["task_status"], server_default="proposed", nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column(
            "depends_on",
            postgresql.ARRAY(sa.UUID()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "contract_ids",
            postgresql.ARRAY(sa.UUID()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
    op.create_index(op.f("ix_tasks_owner_id"), "tasks", ["owner_id"], unique=False)
    op.create_index(op.f("ix_tasks_workspace_id"), "tasks", ["workspace_id"], unique=False)
    op.create_table(
        "approvals",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("approver_id", sa.UUID(), nullable=False),
        sa.Column("decision", ENUMS["approval_decision"], nullable=False),
        sa.Column("candidate_sha", sa.String(length=64), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("merged_sha", sa.String(length=64), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
    op.create_index(op.f("ix_approvals_approver_id"), "approvals", ["approver_id"], unique=False)
    op.create_index(op.f("ix_approvals_run_id"), "approvals", ["run_id"], unique=False)
    op.create_table(
        "check_results",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", ENUMS["check_kind"], nullable=False),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", ENUMS["check_status"], server_default="pending", nullable=False),
        sa.Column("log_path", sa.String(length=1024), nullable=True),
        sa.Column(
            "artifacts_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
    op.create_index(op.f("ix_check_results_run_id"), "check_results", ["run_id"], unique=False)
    op.create_table(
        "submissions",
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("handoff_summary", sa.Text(), server_default="", nullable=False),
        sa.Column("status", ENUMS["submission_status"], server_default="pending", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_submissions_task_id_tasks"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
    )
    op.create_index(op.f("ix_submissions_task_id"), "submissions", ["task_id"], unique=False)
    op.create_table(
        "failures",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("check_result_id", sa.UUID(), nullable=True),
        sa.Column("suspected_task_id", sa.UUID(), nullable=True),
        sa.Column("suspected_contract_id", sa.UUID(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", ENUMS["failure_status"], server_default="open", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
    op.create_index(
        op.f("ix_failures_check_result_id"), "failures", ["check_result_id"], unique=False
    )
    op.create_index(op.f("ix_failures_run_id"), "failures", ["run_id"], unique=False)
    op.create_index(
        op.f("ix_failures_suspected_contract_id"),
        "failures",
        ["suspected_contract_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_failures_suspected_task_id"), "failures", ["suspected_task_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_failures_suspected_task_id"), table_name="failures")
    op.drop_index(op.f("ix_failures_suspected_contract_id"), table_name="failures")
    op.drop_index(op.f("ix_failures_run_id"), table_name="failures")
    op.drop_index(op.f("ix_failures_check_result_id"), table_name="failures")
    op.drop_table("failures")
    op.drop_index(op.f("ix_submissions_task_id"), table_name="submissions")
    op.drop_table("submissions")
    op.drop_index(op.f("ix_check_results_run_id"), table_name="check_results")
    op.drop_table("check_results")
    op.drop_index(op.f("ix_approvals_run_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_approver_id"), table_name="approvals")
    op.drop_table("approvals")
    op.drop_index(op.f("ix_tasks_workspace_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_owner_id"), table_name="tasks")
    op.drop_table("tasks")
    op.drop_index(op.f("ix_spec_versions_workspace_id"), table_name="spec_versions")
    op.drop_table("spec_versions")
    op.drop_index(op.f("ix_spec_items_workspace_id"), table_name="spec_items")
    op.drop_table("spec_items")
    op.drop_index("ix_messages_workspace_id_created_at", table_name="messages")
    op.drop_index(op.f("ix_messages_workspace_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_user_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_members_workspace_id"), table_name="members")
    op.drop_index(op.f("ix_members_user_id"), table_name="members")
    op.drop_table("members")
    op.drop_index(op.f("ix_knowledge_links_workspace_id"), table_name="knowledge_links")
    op.drop_index("ix_knowledge_links_src", table_name="knowledge_links")
    op.drop_index("ix_knowledge_links_dst", table_name="knowledge_links")
    op.drop_table("knowledge_links")
    op.drop_index(op.f("ix_integration_runs_workspace_id"), table_name="integration_runs")
    op.drop_table("integration_runs")
    op.drop_index(op.f("ix_contracts_workspace_id"), table_name="contracts")
    op.drop_table("contracts")
    op.drop_index(op.f("ix_workspaces_owner_id"), table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_table("users")
    op.drop_index("ix_jobs_status_created_at", table_name="jobs")
    op.drop_table("jobs")

    bind = op.get_bind()
    for enum in ENUMS.values():
        enum.drop(bind, checkfirst=False)
