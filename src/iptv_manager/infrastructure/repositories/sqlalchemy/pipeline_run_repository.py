"""SQLAlchemy implementation of domain.ports.PipelineRunRepository."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from iptv_manager.domain.entities.pipeline_run import PipelineRun, PipelineRunStatus
from iptv_manager.infrastructure.repositories.sqlalchemy.models import PipelineRunModel


class SQLAlchemyPipelineRunRepository:
    """Concrete implementation of domain.ports.PipelineRunRepository.

    Every public method is async (to satisfy the port), delegating to
    a synchronous SQLAlchemy Session run in a worker thread via
    asyncio.to_thread - matching the same pattern used by
    LocalFilePlaylistSource for local file I/O.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    async def save(self, run: PipelineRun) -> PipelineRun:
        return await asyncio.to_thread(self._save_sync, run)

    async def update(self, run: PipelineRun) -> PipelineRun:
        return await asyncio.to_thread(self._update_sync, run)

    async def get(self, run_id: int) -> PipelineRun | None:
        return await asyncio.to_thread(self._get_sync, run_id)

    async def list_recent(self, limit: int = 20) -> list[PipelineRun]:
        return await asyncio.to_thread(self._list_recent_sync, limit)

    def _save_sync(self, run: PipelineRun) -> PipelineRun:
        with self._session_factory() as session:
            model = self._to_model(run)
            session.add(model)
            session.commit()
            session.refresh(model)
            return self._to_entity(model)

    def _update_sync(self, run: PipelineRun) -> PipelineRun:
        if run.id is None:
            raise ValueError("cannot update a PipelineRun with id=None; save() it first")
        with self._session_factory() as session:
            model = session.get(PipelineRunModel, run.id)
            if model is None:
                raise ValueError(f"pipeline run {run.id} not found")
            self._apply(run, model)
            session.commit()
            session.refresh(model)
            return self._to_entity(model)

    def _get_sync(self, run_id: int) -> PipelineRun | None:
        with self._session_factory() as session:
            model = session.get(PipelineRunModel, run_id)
            return self._to_entity(model) if model is not None else None

    def _list_recent_sync(self, limit: int) -> list[PipelineRun]:
        with self._session_factory() as session:
            stmt = (
                select(PipelineRunModel)
                .order_by(PipelineRunModel.started_at.desc())
                .limit(limit)
            )
            models = session.scalars(stmt).all()
            return [self._to_entity(m) for m in models]

    def _to_model(self, run: PipelineRun) -> PipelineRunModel:
        model = PipelineRunModel(
            started_at=run.started_at,
            finished_at=run.finished_at,
            status=run.status.value,
            channels_before=run.channels_before,
            channels_after=run.channels_after,
            duplicate_urls_removed=run.duplicate_urls_removed,
            online_count=run.online_count,
            offline_count=run.offline_count,
            logos_reachable=run.logos_reachable,
            logos_missing=run.logos_missing,
            epg_invalid_tvg_id=run.epg_invalid_tvg_id,
            error_message=run.error_message,
        )
        return model

    def _apply(self, run: PipelineRun, model: PipelineRunModel) -> None:
        model.finished_at = run.finished_at
        model.status = run.status.value
        model.channels_before = run.channels_before
        model.channels_after = run.channels_after
        model.duplicate_urls_removed = run.duplicate_urls_removed
        model.online_count = run.online_count
        model.offline_count = run.offline_count
        model.logos_reachable = run.logos_reachable
        model.logos_missing = run.logos_missing
        model.epg_invalid_tvg_id = run.epg_invalid_tvg_id
        model.error_message = run.error_message

    def _to_entity(self, model: PipelineRunModel) -> PipelineRun:
        return PipelineRun(
            id=model.id,
            started_at=model.started_at,
            finished_at=model.finished_at,
            status=PipelineRunStatus(model.status),
            channels_before=model.channels_before,
            channels_after=model.channels_after,
            duplicate_urls_removed=model.duplicate_urls_removed,
            online_count=model.online_count,
            offline_count=model.offline_count,
            logos_reachable=model.logos_reachable,
            logos_missing=model.logos_missing,
            epg_invalid_tvg_id=model.epg_invalid_tvg_id,
            error_message=model.error_message,
        )
