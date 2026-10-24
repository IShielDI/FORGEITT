"""Database schema. Importing this package registers every table on `metadata`."""

from app.models.tables import ROOM_SCOPED, metadata

__all__ = ["ROOM_SCOPED", "metadata"]
