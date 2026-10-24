import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.models.enums import SubmissionStatus


class Submission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "submissions"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    handoff_summary: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    status: Mapped[SubmissionStatus] = mapped_column(
        pg_enum(SubmissionStatus, "submission_status"),
        nullable=False,
        default=SubmissionStatus.PENDING,
        server_default=SubmissionStatus.PENDING.value,
    )
