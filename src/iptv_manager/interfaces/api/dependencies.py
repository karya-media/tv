"""Shared FastAPI dependency providers.

The PipelineRunRepository is created once at app startup (see
interfaces.api.app.lifespan) and stored on app.state, rather than
re-created per request - a SQLAlchemy engine/session factory is meant
to be a long-lived singleton, not something rebuilt on every call.
"""

from __future__ import annotations

from fastapi import Request

from iptv_manager.domain.ports.pipeline_run_repository import PipelineRunRepository


def get_run_repository(request: Request) -> PipelineRunRepository:
    repository: PipelineRunRepository = request.app.state.run_repository
    return repository
