from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.columns import user_fk, workspace_fk


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_workspace_id_created_at", "workspace_id", "created_at"),)

    workspace_id: Mapped[str] = workspace_fk()
    user_id: Mapped[str] = user_fk(nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
