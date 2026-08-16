"""PipelineRun entity.

Represents one execution of the full pipeline (merge -> validate ->
logos -> optional EPG comparison -> report), persisted so the web
dashboard can show run history/trends rather than only the latest
snapshot. This is the one entity in the system backed by a database
table instead of being reconstructed fresh from files each time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class PipelineRunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(slots=True)
class PipelineRun:
    id: int | None
    started_at: datetime
    status: PipelineRunStatus
    finished_at: datetime | None = None
    channels_before: int | None = None
    channels_after: int | None = None
    duplicate_urls_removed: int | None = None
    online_count: int | None = None
    offline_count: int | None = None
    logos_reachable: int | None = None
    logos_missing: int | None = None
    epg_invalid_tvg_id: int | None = None
    error_message: str | None = None
