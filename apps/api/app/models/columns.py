"""Reusable column constructors for common foreign keys and JSON fields."""

from typing import Any

from sqlalchemy import JSON, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUID_LENGTH


def fk(target: str, *, ondelete: str, nullable: bool = False, index: bool = True) -> Mapped[Any]:
    """String UUID foreign key to `target` (e.g. "tasks.id")."""
    return mapped_column(
        String(UUID_LENGTH),
        ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        index=index,
    )


def workspace_fk() -> Mapped[str]:
    """Indexed, cascading reference to the owning workspace."""
    return fk("workspaces.id", ondelete="CASCADE")


def user_fk(*, nullable: bool, index: bool = True) -> Mapped[Any]:
    """Reference to a user. Users with history cannot be deleted (RESTRICT) unless nullable."""
    return fk(
        "users.id", ondelete="SET NULL" if nullable else "RESTRICT", nullable=nullable, index=index
    )


def id_list() -> Mapped[list[str]]:
    """JSON array of string ids, e.g. source_message_ids or depends_on."""
    return mapped_column(JSON, nullable=False, default=list, server_default=text("'[]'"))


def json_object() -> Mapped[dict[str, Any]]:
    return mapped_column(JSON, nullable=False, default=dict, server_default=text("'{}'"))
