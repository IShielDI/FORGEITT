from sqlalchemy import CheckConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.columns import workspace_fk
from app.models.enums import ContractKind, ContractStatus


class Contract(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Versioned API/schema/type contract. Each edit is a new row with version + 1."""

    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", "version"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    workspace_id: Mapped[str] = workspace_fk()
    kind: Mapped[ContractKind] = mapped_column(str_enum(ContractKind, "contract_kind"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[ContractStatus] = mapped_column(
        str_enum(ContractStatus, "contract_status"),
        nullable=False,
        default=ContractStatus.PROPOSED,
        server_default=ContractStatus.PROPOSED.value,
    )
