"""Tests that the background scheduler is wired correctly: started
when IPTV_SCHEDULER_ENABLED=true, absent otherwise. Doesn't wait for a
real interval to fire - just checks the job is registered with
APScheduler, which is what actually matters for correctness.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from iptv_manager.config.settings import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    yield
    get_settings.cache_clear()


def test_scheduler_disabled_by_default(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IPTV_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("IPTV_API_KEY", "k")
    monkeypatch.setenv("IPTV_GITHUB_REPOSITORY", "")
    get_settings.cache_clear()

    from iptv_manager.interfaces.api.app import app

    with TestClient(app):
        assert app.state.scheduler is None


def test_scheduler_starts_when_enabled(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IPTV_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("IPTV_API_KEY", "k")
    monkeypatch.setenv("IPTV_GITHUB_REPOSITORY", "")
    monkeypatch.setenv("IPTV_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("IPTV_SCHEDULER_INTERVAL_MINUTES", "60")
    get_settings.cache_clear()

    from iptv_manager.interfaces.api.app import app

    with TestClient(app):
        assert app.state.scheduler is not None
        job = app.state.scheduler.get_job("iptv_pipeline")
        assert job is not None
        assert job.trigger.interval.total_seconds() == 60 * 60
