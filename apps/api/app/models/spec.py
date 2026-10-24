from typing import Any

from sqlalchemy import CheckConstraint, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.columns import id_list, json_object, user_fk, workspace_fk
from app.models.enums import SpecItemKind, SpecItemStatus


class SpecItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A requirement/decision/suggestion/question. Confirmed items are append-only (TRD 3)."""

    __tablename__ = "spec_items"
    __table_args__ = (CheckConstraint("version >= 1", name="version_positive"),)

    workspace_id: Mapped[str] = workspace_fk()
    kind: Mapped[SpecItemKind] = mapped_column(str_enum(SpecItemKind, "spec_item_kind"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SpecItemStatus] = mapped_column(
        str_enum(SpecItemStatus, "spec_item_status"),
        nullable=False,
        default=SpecItemStatus.PROPOSED,
        server_default=SpecItemStatus.PROPOSED.value,
    )
    source_message_ids: Mapped[list[str]] = id_list()
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    # Null created_by means the observer agent proposed it; confirmed_by is always a human.
    created_by: Mapped[str | None] = user_fk(nullable=True, index=False)
    confirmed_by: Mapped[str | None] = user_fk(nullable=True, index=False)


class SpecVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable snapshot of the whole spec at a version number."""

    __tablename__ = "spec_versions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "version"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    workspace_id: Mapped[str] = workspace_fk()
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = json_object()
