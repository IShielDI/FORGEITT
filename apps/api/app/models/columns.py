"""Reusable column constructors for common foreign keys and Postgres types."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


def workspace_fk() -> Mapped[uuid.UUID]:
    """Indexed, cascading reference to the owning workspace."""
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )


def user_fk(*, nullable: bool, index: bool = False) -> Mapped[Any]:
    """Reference to a user. Users with history cannot be deleted (RESTRICT) unless nullable."""
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL" if nullable else "RESTRICT"),
        nullable=nullable,
        index=index,
    )


def uuid_array() -> Mapped[list[uuid.UUID]]:
    return mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default=text("'{}'")
    )


def jsonb_object() -> Mapped[dict[str, Any]]:
    return mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
