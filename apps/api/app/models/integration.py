import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.models.columns import jsonb_object, workspace_fk
from app.models.enums import CheckKind, CheckStatus, FailureStatus, RunStatus, VerificationProfile


def run_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integration_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )


class IntegrationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One mirror build of `candidate/<run_id>` from main plus submitted task branches."""

    __tablename__ = "integration_runs"

    workspace_id: Mapped[uuid.UUID] = workspace_fk()
    candidate_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        pg_enum(RunStatus, "run_status"),
        nullable=False,
        default=RunStatus.QUEUED,
        server_default=RunStatus.QUEUED.value,
    )
    profile: Mapped[VerificationProfile] = mapped_column(
        pg_enum(VerificationProfile, "verification_profile"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CheckResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Evidence for one check. Verdicts derive only from exit_code and artifacts (TRD R6)."""

    __tablename__ = "check_results"

    run_id: Mapped[uuid.UUID] = run_fk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[CheckKind] = mapped_column(pg_enum(CheckKind, "check_kind"))
    # TRD R6 requires recording the command and duration alongside the exit code.
    command: Mapped[str | None] = mapped_column(Text)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[CheckStatus] = mapped_column(
        pg_enum(CheckStatus, "check_status"),
        nullable=False,
        default=CheckStatus.PENDING,
        server_default=CheckStatus.PENDING.value,
    )
    log_path: Mapped[str | None] = mapped_column(String(1024))
    artifacts_json: Mapped[dict[str, Any]] = jsonb_object()


class Failure(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A suspected cause for a failing check. Confidence is never certainty (TRD R8)."""

    __tablename__ = "failures"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )

    run_id: Mapped[uuid.UUID] = run_fk()
    check_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("check_results.id", ondelete="CASCADE"), index=True
    )
    suspected_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    suspected_contract_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="SET NULL"), index=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_json: Mapped[dict[str, Any]] = jsonb_object()
    status: Mapped[FailureStatus] = mapped_column(
        pg_enum(FailureStatus, "failure_status"),
        nullable=False,
        default=FailureStatus.OPEN,
        server_default=FailureStatus.OPEN.value,
    )
