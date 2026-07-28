"""Pydantic response models for the REST API.

Kept separate from the domain entity (PipelineRun) even though the
fields largely mirror each other: this is the API's public contract,
which should be free to evolve independently of the internal entity
shape (e.g. renaming a field, hiding an internal-only one) without
that being a breaking domain change.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from iptv_manager.domain.entities.pipeline_run import PipelineRun, PipelineRunStatus


class PipelineRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    finished_at: datetime | None
    status: PipelineRunStatus
    channels_before: int | None
    channels_after: int | None
    duplicate_urls_removed: int | None
    online_count: int | None
    offline_count: int | None
    logos_reachable: int | None
    logos_missing: int | None
    epg_invalid_tvg_id: int | None
    error_message: str | None

    @classmethod
    def from_entity(cls, run: PipelineRun) -> PipelineRunOut:
        return cls.model_validate(run, from_attributes=True)


class TriggerRunResponse(BaseModel):
    run_id: int
    status: PipelineRunStatus
