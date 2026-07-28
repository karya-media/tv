"""Port: persisting and retrieving PipelineRun history.

infrastructure.repositories.sqlalchemy.SQLAlchemyPipelineRunRepository
is the concrete implementation. Kept as a Protocol so the API layer
and its tests can swap in an in-memory fake without touching a real
database.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from iptv_manager.domain.entities.pipeline_run import PipelineRun


@runtime_checkable
class PipelineRunRepository(Protocol):
    async def save(self, run: PipelineRun) -> PipelineRun: ...

    async def update(self, run: PipelineRun) -> PipelineRun: ...

    async def get(self, run_id: int) -> PipelineRun | None: ...

    async def list_recent(self, limit: int = 20) -> list[PipelineRun]: ...
