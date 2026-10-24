from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.columns import user_fk, workspace_fk
from app.models.enums import MemberRole
from app.models.workspace import TOKEN_HASH_LENGTH


class Invite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Single-use invite link (TRD R14). Only the token hash is stored."""

    __tablename__ = "invites"
    __table_args__ = (
        CheckConstraint("(used_at IS NULL) = (used_by IS NULL)", name="used_at_and_by_together"),
    )

    workspace_id: Mapped[str] = workspace_fk()
    token_hash: Mapped[str] = mapped_column(String(TOKEN_HASH_LENGTH), nullable=False, unique=True)
    role: Mapped[MemberRole] = mapped_column(
        str_enum(MemberRole, "member_role"),
        nullable=False,
        default=MemberRole.MEMBER,
        server_default=MemberRole.MEMBER.value,
    )
    created_by: Mapped[str] = user_fk(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[str | None] = user_fk(nullable=True)
