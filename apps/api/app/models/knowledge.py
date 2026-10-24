from sqlalchemy import CheckConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUID_LENGTH, Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.columns import workspace_fk
from app.models.enums import EntityType


class KnowledgeLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Typed, versioned edge between two knowledge entities (ARCHITECTURE section 8)."""

    __tablename__ = "knowledge_links"
    __table_args__ = (
        Index("ix_knowledge_links_src", "src_type", "src_id"),
        Index("ix_knowledge_links_dst", "dst_type", "dst_id"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    workspace_id: Mapped[str] = workspace_fk()
    src_type: Mapped[EntityType] = mapped_column(str_enum(EntityType, "src_type"))
    src_id: Mapped[str] = mapped_column(String(UUID_LENGTH), nullable=False)
    dst_type: Mapped[EntityType] = mapped_column(str_enum(EntityType, "dst_type"))
    dst_id: Mapped[str] = mapped_column(String(UUID_LENGTH), nullable=False)
    relation: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
