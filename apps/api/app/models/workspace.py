import uuid

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.models.columns import user_fk, workspace_fk
from app.models.enums import MemberRole, VerificationProfile


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    room_code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_id: Mapped[uuid.UUID] = user_fk(nullable=False, index=True)
    verification_profile: Mapped[VerificationProfile] = mapped_column(
        pg_enum(VerificationProfile, "verification_profile"),
        nullable=False,
        default=VerificationProfile.LIGHT,
        server_default=VerificationProfile.LIGHT.value,
    )


class Member(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    workspace_id: Mapped[uuid.UUID] = workspace_fk()
    user_id: Mapped[uuid.UUID] = user_fk(nullable=False, index=True)
    role: Mapped[MemberRole] = mapped_column(
        pg_enum(MemberRole, "member_role"),
        nullable=False,
        default=MemberRole.MEMBER,
        server_default=MemberRole.MEMBER.value,
    )
