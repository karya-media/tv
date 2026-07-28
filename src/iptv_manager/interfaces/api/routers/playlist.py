"""Serves the master playlist and generated reports directly from this
process - a self-hosted alternative to the GitHub raw/Pages URLs, for
people running the API instead of (or alongside) GitHub Actions.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from iptv_manager.config.settings import Settings, get_settings

router = APIRouter(tags=["playlist"])

_REPORT_FILES = {
    "html": ("report.html", "text/html"),
    "json": ("report.json", "application/json"),
    "csv": ("report.csv", "text/csv"),
    "xlsx": (
        "report.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
}


@router.get("/playlist/master.m3u")
def get_master_playlist(settings: Settings = Depends(get_settings)) -> FileResponse:
    if not settings.master_playlist_path.is_file():
        raise HTTPException(status_code=404, detail="master playlist not generated yet")
    return FileResponse(
        settings.master_playlist_path,
        media_type="application/vnd.apple.mpegurl",
        filename="master.m3u",
    )


@router.get("/api/reports/{fmt}")
def get_report(fmt: str, settings: Settings = Depends(get_settings)) -> FileResponse:
    if fmt not in _REPORT_FILES:
        raise HTTPException(status_code=404, detail=f"unknown report format: {fmt}")
    filename, media_type = _REPORT_FILES[fmt]
    path = settings.project_root / settings.reports_dir / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"report not generated yet: {filename}")
    return FileResponse(path, media_type=media_type, filename=filename)
