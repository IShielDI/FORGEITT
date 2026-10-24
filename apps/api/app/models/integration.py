from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.columns import fk, json_object, workspace_fk
from app.models.enums import CheckKind, CheckStatus, FailureStatus, RunStatus, VerificationProfile


def run_fk() -> Mapped[str]:
    return fk("integration_runs.id", ondelete="CASCADE")


class IntegrationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One mirror build of `candidate/<run_id>` from main plus submitted task branches."""

    __tablename__ = "integration_runs"

    workspace_id: Mapped[str] = workspace_fk()
    candidate_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        str_enum(RunStatus, "run_status"),
        nullable=False,
        default=RunStatus.QUEUED,
        server_default=RunStatus.QUEUED.value,
    )
    profile: Mapped[VerificationProfile] = mapped_column(
        str_enum(VerificationProfile, "verification_profile"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CheckResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Evidence for one check. Verdicts derive only from exit_code and artifacts (TRD R6)."""

    __tablename__ = "check_results"

    run_id: Mapped[str] = run_fk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[CheckKind] = mapped_column(str_enum(CheckKind, "check_kind"))
    # Stage 16 records the command and duration alongside the exit code.
    command: Mapped[str | None] = mapped_column(Text)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[CheckStatus] = mapped_column(
        str_enum(CheckStatus, "check_status"),
        nullable=False,
        default=CheckStatus.PENDING,
        server_default=CheckStatus.PENDING.value,
    )
    log_path: Mapped[str | None] = mapped_column(String(1024))
    artifacts_json: Mapped[dict[str, Any]] = json_object()


class Failure(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A suspected cause for a failing check. Confidence is never certainty (TRD R8)."""

    __tablename__ = "failures"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )

    run_id: Mapped[str] = run_fk()
    check_result_id: Mapped[str | None] = fk("check_results.id", ondelete="CASCADE", nullable=True)
    suspected_task_id: Mapped[str | None] = fk("tasks.id", ondelete="SET NULL", nullable=True)
    suspected_contract_id: Mapped[str | None] = fk(
        "contracts.id", ondelete="SET NULL", nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_json: Mapped[dict[str, Any]] = json_object()
    status: Mapped[FailureStatus] = mapped_column(
        str_enum(FailureStatus, "failure_status"),
        nullable=False,
        default=FailureStatus.OPEN,
        server_default=FailureStatus.OPEN.value,
    )
