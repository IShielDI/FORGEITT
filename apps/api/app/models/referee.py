from datetime import datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.columns import json_object
from app.models.enums import RefereeVerdict
from app.models.integration import run_fk


class RefereeRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """TinyFish verdict on the running candidate (TRD R11). Defaults to `not_run`, never pass."""

    __tablename__ = "referee_runs"

    run_id: Mapped[str] = run_fk()
    verdict: Mapped[RefereeVerdict] = mapped_column(
        str_enum(RefereeVerdict, "referee_verdict"),
        nullable=False,
        default=RefereeVerdict.NOT_RUN,
        server_default=RefereeVerdict.NOT_RUN.value,
    )
    evidence_json: Mapped[dict[str, Any]] = json_object()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
