"""Read-only HTML dashboard: recent pipeline run history and links to
download the latest reports / master playlist.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from iptv_manager.domain.ports.pipeline_run_repository import PipelineRunRepository
from iptv_manager.interfaces.api.dependencies import get_run_repository
from iptv_manager.interfaces.api.security import optional_dashboard_auth

router = APIRouter(tags=["dashboard"])

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)


@router.get("/", response_class=HTMLResponse, dependencies=[Depends(optional_dashboard_auth)])
async def dashboard_home(
    request: Request,
    run_repository: PipelineRunRepository = Depends(get_run_repository),
) -> HTMLResponse:
    runs = await run_repository.list_recent(limit=20)
    template = _env.get_template("dashboard.html.j2")
    return HTMLResponse(template.render(runs=runs, request=request))
