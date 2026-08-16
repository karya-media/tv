"""API endpoints for triggering and inspecting pipeline runs."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from iptv_manager.config.settings import Settings, get_settings
from iptv_manager.domain.ports.pipeline_run_repository import PipelineRunRepository
from iptv_manager.interfaces.api.dependencies import get_run_repository
from iptv_manager.interfaces.api.pipeline_runner import create_running_run, execute_and_persist
from iptv_manager.interfaces.api.schemas import PipelineRunOut, TriggerRunResponse
from iptv_manager.interfaces.api.security import require_api_key

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post(
    "/run",
    response_model=TriggerRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key)],
)
async def trigger_pipeline_run(
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
    run_repository: PipelineRunRepository = Depends(get_run_repository),
) -> TriggerRunResponse:
    """Kick off the full pipeline in the background and return
    immediately with a run id the caller can poll via GET
    /api/pipeline/runs/{run_id}."""
    run = await create_running_run(run_repository)
    assert run.id is not None  # save() always persists and assigns an id
    background_tasks.add_task(
        execute_and_persist, run, settings=settings, run_repository=run_repository
    )
    return TriggerRunResponse(run_id=run.id, status=run.status)


@router.get("/runs", response_model=list[PipelineRunOut])
async def list_pipeline_runs(
    limit: int = 20,
    run_repository: PipelineRunRepository = Depends(get_run_repository),
) -> list[PipelineRunOut]:
    runs = await run_repository.list_recent(limit=limit)
    return [PipelineRunOut.from_entity(r) for r in runs]


@router.get("/runs/{run_id}", response_model=PipelineRunOut)
async def get_pipeline_run(
    run_id: int,
    run_repository: PipelineRunRepository = Depends(get_run_repository),
) -> PipelineRunOut:
    run = await run_repository.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"pipeline run {run_id} not found")
    return PipelineRunOut.from_entity(run)
