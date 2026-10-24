from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.columns import user_fk, workspace_fk
from app.models.enums import HiddenTestStatus


class HiddenTest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Human-written test kept outside any agent-readable path (TRD R12).

    Only the location is stored here; the test source never enters the database.
    """

    __tablename__ = "hidden_tests"

    workspace_id: Mapped[str] = workspace_fk()
    author_id: Mapped[str] = user_fk(nullable=False)
    approved_by: Mapped[str | None] = user_fk(nullable=True)
    location: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[HiddenTestStatus] = mapped_column(
        str_enum(HiddenTestStatus, "hidden_test_status"),
        nullable=False,
        default=HiddenTestStatus.DRAFT,
        server_default=HiddenTestStatus.DRAFT.value,
    )
