from decimal import Decimal

from sqlalchemy import Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.columns import fk, user_fk, workspace_fk
from app.models.enums import CreditKind


class CreditLedger(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only credits ledger (TRD R13). Every model call writes a `usage` row."""

    __tablename__ = "credit_ledger"
    __table_args__ = (Index("ix_credit_ledger_workspace_id_user_id", "workspace_id", "user_id"),)

    workspace_id: Mapped[str] = workspace_fk()
    user_id: Mapped[str | None] = user_fk(nullable=True)
    kind: Mapped[CreditKind] = mapped_column(str_enum(CreditKind, "credit_kind"))
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    task_id: Mapped[str | None] = fk("tasks.id", ondelete="SET NULL", nullable=True)
