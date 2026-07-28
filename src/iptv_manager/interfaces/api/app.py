"""FastAPI application factory.

Wires together the REST API, the read-only dashboard, and (if
IPTV_SCHEDULER_ENABLED=true) a background APScheduler that re-runs the
full pipeline on a timer - useful for self-hosted deployments that
don't rely on GitHub Actions for scheduling.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from iptv_manager.config.settings import get_settings
from iptv_manager.infrastructure.repositories.sqlalchemy.database import (
    create_db_engine,
    init_db,
    make_session_factory,
)
from iptv_manager.infrastructure.repositories.sqlalchemy.pipeline_run_repository import (
    SQLAlchemyPipelineRunRepository,
)
from iptv_manager.interfaces.api.pipeline_runner import scheduled_pipeline_job
from iptv_manager.interfaces.api.routers import dashboard, pipeline, playlist


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.ensure_directories()

    engine = create_db_engine(settings.resolved_database_url)
    init_db(engine)
    app.state.run_repository = SQLAlchemyPipelineRunRepository(make_session_factory(engine))
    app.state.settings = settings

    scheduler: AsyncIOScheduler | None = None
    if settings.scheduler_enabled:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            scheduled_pipeline_job,
            "interval",
            minutes=settings.scheduler_interval_minutes,
            kwargs={"settings": settings, "run_repository": app.state.run_repository},
            id="iptv_pipeline",
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
    app.state.scheduler = scheduler

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    fastapi_app = FastAPI(title="IPTV Playlist Manager", lifespan=lifespan)
    fastapi_app.include_router(pipeline.router)
    fastapi_app.include_router(playlist.router)
    fastapi_app.include_router(dashboard.router)
    return fastapi_app


app = create_app()
