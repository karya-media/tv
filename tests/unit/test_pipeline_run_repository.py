"""Unit tests for SQLAlchemyPipelineRunRepository, run against a real
temporary SQLite database file (not mocked) so the actual SQL and
schema are exercised.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from iptv_manager.domain.entities.pipeline_run import PipelineRun, PipelineRunStatus
from iptv_manager.infrastructure.repositories.sqlalchemy.database import (
    create_db_engine,
    init_db,
    make_session_factory,
)
from iptv_manager.infrastructure.repositories.sqlalchemy.pipeline_run_repository import (
    SQLAlchemyPipelineRunRepository,
)


@pytest.fixture
def repository(tmp_path: Path) -> SQLAlchemyPipelineRunRepository:
    db_path = tmp_path / "test.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(engine)
    return SQLAlchemyPipelineRunRepository(make_session_factory(engine))


def _new_run(status: PipelineRunStatus = PipelineRunStatus.RUNNING) -> PipelineRun:
    return PipelineRun(id=None, started_at=datetime.now(timezone.utc), status=status)


@pytest.mark.asyncio
async def test_save_assigns_an_id(repository: SQLAlchemyPipelineRunRepository):
    saved = await repository.save(_new_run())
    assert saved.id is not None


@pytest.mark.asyncio
async def test_get_returns_saved_run(repository: SQLAlchemyPipelineRunRepository):
    saved = await repository.save(_new_run())
    fetched = await repository.get(saved.id)
    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.status == PipelineRunStatus.RUNNING


@pytest.mark.asyncio
async def test_get_nonexistent_returns_none(repository: SQLAlchemyPipelineRunRepository):
    assert await repository.get(999999) is None


@pytest.mark.asyncio
async def test_update_persists_changes(repository: SQLAlchemyPipelineRunRepository):
    saved = await repository.save(_new_run())
    saved.status = PipelineRunStatus.SUCCESS
    saved.channels_after = 42
    saved.finished_at = datetime.now(timezone.utc)

    updated = await repository.update(saved)
    assert updated.status == PipelineRunStatus.SUCCESS
    assert updated.channels_after == 42

    refetched = await repository.get(saved.id)
    assert refetched.status == PipelineRunStatus.SUCCESS
    assert refetched.channels_after == 42


@pytest.mark.asyncio
async def test_update_unsaved_run_raises(repository: SQLAlchemyPipelineRunRepository):
    with pytest.raises(ValueError):
        await repository.update(_new_run())


@pytest.mark.asyncio
async def test_update_nonexistent_id_raises(repository: SQLAlchemyPipelineRunRepository):
    ghost = _new_run()
    ghost.id = 999999
    with pytest.raises(ValueError):
        await repository.update(ghost)


@pytest.mark.asyncio
async def test_list_recent_orders_newest_first(repository: SQLAlchemyPipelineRunRepository):
    import asyncio

    first = await repository.save(
        PipelineRun(id=None, started_at=datetime(2026, 1, 1, tzinfo=timezone.utc), status=PipelineRunStatus.SUCCESS)
    )
    await asyncio.sleep(0)  # yield control, no real ordering dependency needed
    second = await repository.save(
        PipelineRun(id=None, started_at=datetime(2026, 1, 2, tzinfo=timezone.utc), status=PipelineRunStatus.SUCCESS)
    )

    runs = await repository.list_recent(limit=10)
    assert [r.id for r in runs] == [second.id, first.id]


@pytest.mark.asyncio
async def test_list_recent_respects_limit(repository: SQLAlchemyPipelineRunRepository):
    for _ in range(5):
        await repository.save(_new_run())
    runs = await repository.list_recent(limit=2)
    assert len(runs) == 2


@pytest.mark.asyncio
async def test_error_message_round_trips(repository: SQLAlchemyPipelineRunRepository):
    run = _new_run()
    saved = await repository.save(run)
    saved.status = PipelineRunStatus.FAILED
    saved.error_message = "no category playlists found"
    updated = await repository.update(saved)
    assert updated.error_message == "no category playlists found"
