from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.columns import id_list, user_fk, workspace_fk
from app.models.enums import TaskStatus


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    workspace_id: Mapped[str] = workspace_fk()
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    owner_id: Mapped[str | None] = user_fk(nullable=True)
    component: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[TaskStatus] = mapped_column(
        str_enum(TaskStatus, "task_status"),
        nullable=False,
        default=TaskStatus.PROPOSED,
        server_default=TaskStatus.PROPOSED.value,
    )
    branch: Mapped[str | None] = mapped_column(String(255))
    depends_on: Mapped[list[str]] = id_list()
    contract_ids: Mapped[list[str]] = id_list()
