from typing import Any

from sqlalchemy import CheckConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.models.columns import jsonb_object
from app.models.enums import JobStatus


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """DB-backed job queue row for the in-process worker."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_created_at", "status", "created_at"),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
    )

    type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = jsonb_object()
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"),
        nullable=False,
        default=JobStatus.QUEUED,
        server_default=JobStatus.QUEUED.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
