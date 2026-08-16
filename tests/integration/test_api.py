"""Integration tests for the FastAPI app (interfaces.api.app), run
against a real temporary project directory and a real SQLite database
- no mocking of the app's own wiring. Stream/logo validation still
happen for real over HTTP during these tests, but the destination
(example.com) is unreachable in the test sandbox, which is fine: the
point here is to prove the API/auth/persistence plumbing works, not to
re-verify stream validation logic (already covered in Phase 3 tests).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from iptv_manager.config.settings import get_settings

SPORTS_M3U = (
    "#EXTM3U\n"
    '#EXTINF:-1 tvg-id="espn.us" group-title="Sports",ESPN HD\n'
    "http://example.com/stream/espn.m3u8\n"
)


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IPTV_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("IPTV_API_KEY", "test-api-key")
    monkeypatch.setenv("IPTV_GITHUB_REPOSITORY", "")
    monkeypatch.setenv("IPTV_DASHBOARD_USERNAME", "")
    monkeypatch.setenv("IPTV_DASHBOARD_PASSWORD", "")
    get_settings.cache_clear()

    settings = get_settings()
    settings.ensure_directories()
    (settings.categories_path / "sports.m3u").write_text(SPORTS_M3U, encoding="utf-8")

    from iptv_manager.interfaces.api.app import app

    with TestClient(app) as client:
        yield client

    get_settings.cache_clear()


def test_dashboard_loads_when_no_auth_configured(api_client: TestClient):
    response = api_client.get("/")
    assert response.status_code == 200
    assert "IPTV Playlist Manager" in response.text


def test_trigger_without_api_key_is_rejected(api_client: TestClient):
    response = api_client.post("/api/pipeline/run")
    assert response.status_code == 401


def test_trigger_with_wrong_api_key_is_rejected(api_client: TestClient):
    response = api_client.post("/api/pipeline/run", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_trigger_with_correct_api_key_succeeds(api_client: TestClient):
    response = api_client.post("/api/pipeline/run", headers={"X-API-Key": "test-api-key"})
    assert response.status_code == 202
    body = response.json()
    assert "run_id" in body


def test_triggered_run_appears_in_history_and_completes(api_client: TestClient):
    trigger = api_client.post("/api/pipeline/run", headers={"X-API-Key": "test-api-key"})
    run_id = trigger.json()["run_id"]

    detail = api_client.get(f"/api/pipeline/runs/{run_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["status"] in ("success", "failed")  # not still "running"
    assert data["channels_before"] == 1


def test_list_runs_returns_history(api_client: TestClient):
    api_client.post("/api/pipeline/run", headers={"X-API-Key": "test-api-key"})
    api_client.post("/api/pipeline/run", headers={"X-API-Key": "test-api-key"})

    response = api_client.get("/api/pipeline/runs")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_nonexistent_run_returns_404(api_client: TestClient):
    response = api_client.get("/api/pipeline/runs/999999")
    assert response.status_code == 404


def test_master_playlist_served_after_run(api_client: TestClient):
    api_client.post("/api/pipeline/run", headers={"X-API-Key": "test-api-key"})
    response = api_client.get("/playlist/master.m3u")
    assert response.status_code == 200
    assert response.text.startswith("#EXTM3U")


def test_master_playlist_404_before_any_run(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IPTV_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("IPTV_API_KEY", "test-api-key")
    monkeypatch.setenv("IPTV_GITHUB_REPOSITORY", "")
    get_settings.cache_clear()
    get_settings().ensure_directories()

    from iptv_manager.interfaces.api.app import app

    with TestClient(app) as client:
        response = client.get("/playlist/master.m3u")
        assert response.status_code == 404
    get_settings.cache_clear()


def test_report_served_after_run(api_client: TestClient):
    api_client.post("/api/pipeline/run", headers={"X-API-Key": "test-api-key"})
    response = api_client.get("/api/reports/json")
    assert response.status_code == 200


def test_unknown_report_format_returns_404(api_client: TestClient):
    response = api_client.get("/api/reports/pdf")
    assert response.status_code == 404


def test_dashboard_protected_when_credentials_configured(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IPTV_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("IPTV_API_KEY", "test-api-key")
    monkeypatch.setenv("IPTV_GITHUB_REPOSITORY", "")
    monkeypatch.setenv("IPTV_DASHBOARD_USERNAME", "admin")
    monkeypatch.setenv("IPTV_DASHBOARD_PASSWORD", "secret")
    get_settings.cache_clear()
    get_settings().ensure_directories()

    from iptv_manager.interfaces.api.app import app

    with TestClient(app) as client:
        no_auth = client.get("/")
        assert no_auth.status_code == 401

        wrong_auth = client.get("/", auth=("admin", "wrong"))
        assert wrong_auth.status_code == 401

        right_auth = client.get("/", auth=("admin", "secret"))
        assert right_auth.status_code == 200
    get_settings.cache_clear()
