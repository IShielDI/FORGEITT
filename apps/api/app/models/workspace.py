from sqlalchemy import JSON, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.columns import user_fk, workspace_fk
from app.models.enums import MemberRole, VerificationProfile

TOKEN_HASH_LENGTH = 64  # hex SHA-256


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Display label only. Never a credential and never used to join (TRD R14).
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[str] = user_fk(nullable=False)
    verification_profile: Mapped[VerificationProfile] = mapped_column(
        str_enum(VerificationProfile, "verification_profile"),
        nullable=False,
        default=VerificationProfile.FAST,
        server_default=VerificationProfile.FAST.value,
    )
    allowed_providers: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )


class Member(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    workspace_id: Mapped[str] = workspace_fk()
    user_id: Mapped[str] = user_fk(nullable=False)
    role: Mapped[MemberRole] = mapped_column(
        str_enum(MemberRole, "member_role"),
        nullable=False,
        default=MemberRole.MEMBER,
        server_default=MemberRole.MEMBER.value,
    )
    # Hash of the per-member access token; the raw token is shown once and never stored.
    token_hash: Mapped[str | None] = mapped_column(String(TOKEN_HASH_LENGTH), unique=True)
