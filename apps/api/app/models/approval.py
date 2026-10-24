from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.columns import user_fk
from app.models.enums import ApprovalDecision
from app.models.integration import run_fk


class Approval(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Recorded human decision on a run. The Merge Service requires one before writing main."""

    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(
            "merged_sha IS NULL OR decision = 'approved'", name="merged_only_if_approved"
        ),
    )

    run_id: Mapped[str] = run_fk()
    approver_id: Mapped[str] = user_fk(nullable=False)
    # TRD R4: approval is bound to the run's exact candidate SHA.
    candidate_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[ApprovalDecision] = mapped_column(
        str_enum(ApprovalDecision, "approval_decision")
    )
    comment: Mapped[str | None] = mapped_column(Text)
    merged_sha: Mapped[str | None] = mapped_column(String(64))
