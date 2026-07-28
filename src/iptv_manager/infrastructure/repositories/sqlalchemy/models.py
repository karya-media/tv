"""SQLAlchemy ORM models.

Only one table so far: pipeline_runs, tracking history of full
pipeline executions (see domain.entities.pipeline_run.PipelineRun).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PipelineRunModel(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    channels_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duplicate_urls_removed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    online_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offline_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    logos_reachable: Mapped[int | None] = mapped_column(Integer, nullable=True)
    logos_missing: Mapped[int | None] = mapped_column(Integer, nullable=True)
    epg_invalid_tvg_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
