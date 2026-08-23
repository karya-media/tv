"""Integration test: the `iptv-manager report` CLI command end-to-end
against real files in a temp directory. Stream/logo validation is
skipped (--skip-streams --skip-logos) to keep this test hermetic (no
real network calls), matching how a user would run a fast dry-run.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

import iptv_manager.interfaces.cli.main as cli_main
from iptv_manager.config.settings import Settings, get_settings

runner = CliRunner()

SPORTS_M3U = (
    "#EXTM3U\n"
    '#EXTINF:-1 tvg-id="espn.us" group-title="Sports",ESPN HD\n'
    "http://example.com/stream/espn.m3u8\n"
)
NEWS_M3U = (
    "#EXTM3U\n"
    '#EXTINF:-1 tvg-id="cnn.us" group-title="News",CNN\n'
    "http://example.com/stream/cnn.m3u8\n"
)


@pytest.fixture
def isolated_settings(tmp_path: Path, monkeypatch):
    get_settings.cache_clear()
    settings = Settings(project_root=tmp_path, github_repository=None)
    settings.ensure_directories()
    (settings.categories_path / "sports.m3u").write_text(SPORTS_M3U, encoding="utf-8")
    (settings.categories_path / "news.m3u").write_text(NEWS_M3U, encoding="utf-8")
    monkeypatch.setattr(cli_main, "get_settings", lambda: settings)
    yield settings
    get_settings.cache_clear()


def test_report_command_writes_all_requested_formats(isolated_settings: Settings):
    result = runner.invoke(
        cli_main.app, ["report", "--skip-streams", "--skip-logos", "--formats", "html,json"]
    )
    assert result.exit_code == 0, result.output

    reports_dir = isolated_settings.project_root / isolated_settings.reports_dir
    assert (reports_dir / "report.html").exists()
    assert (reports_dir / "report.json").exists()
    assert not (reports_dir / "report.csv").exists()
    assert not (reports_dir / "report.xlsx").exists()


def test_report_command_default_formats_writes_all_four(isolated_settings: Settings):
    result = runner.invoke(cli_main.app, ["report", "--skip-streams", "--skip-logos"])
    assert result.exit_code == 0, result.output

    reports_dir = isolated_settings.project_root / isolated_settings.reports_dir
    for filename in ("report.html", "report.json", "report.csv", "report.xlsx"):
        assert (reports_dir / filename).exists(), filename


def test_report_command_also_writes_master_playlist(isolated_settings: Settings):
    runner.invoke(cli_main.app, ["report", "--skip-streams", "--skip-logos"])
    assert isolated_settings.master_playlist_path.exists()


def test_report_command_rejects_unknown_format(isolated_settings: Settings):
    result = runner.invoke(
        cli_main.app,
        ["report", "--skip-streams", "--skip-logos", "--formats", "html,pdf"],
    )
    assert result.exit_code == 1


def test_report_command_with_epg_populates_epg_section(isolated_settings: Settings, tmp_path: Path):
    epg_path = tmp_path / "epg.xml"
    epg_path.write_text(
        '<tv><channel id="espn.us"><display-name>ESPN</display-name></channel></tv>',
        encoding="utf-8",
    )
    result = runner.invoke(
        cli_main.app,
        [
            "report",
            "--skip-streams",
            "--skip-logos",
            "--formats",
            "json",
            "--epg",
            str(epg_path),
        ],
    )
    assert result.exit_code == 0, result.output

    import json

    reports_dir = isolated_settings.project_root / isolated_settings.reports_dir
    data = json.loads((reports_dir / "report.json").read_text(encoding="utf-8"))
    assert "epg" in data
    # cnn.us has no matching EPG entry in this minimal fixture -> invalid.
    assert any(c["tvg_id"] == "cnn.us" for c in data["epg"]["invalid_tvg_id"])


def test_report_command_fails_cleanly_with_no_categories(tmp_path: Path, monkeypatch):
    get_settings.cache_clear()
    settings = Settings(project_root=tmp_path, github_repository=None)
    settings.ensure_directories()
    monkeypatch.setattr(cli_main, "get_settings", lambda: settings)

    result = runner.invoke(cli_main.app, ["report", "--skip-streams", "--skip-logos"])
    assert result.exit_code == 1
    get_settings.cache_clear()


def test_report_command_survives_a_broken_epg_source(isolated_settings: Settings, tmp_path: Path):
    """A slow/unreachable/malformed EPG source must not take down the
    whole report - the merge/stream/logo results are still valid and
    worth publishing. Simulated here with a nonexistent local path,
    which raises the same PlaylistFetchError family a real network
    failure or timeout would."""
    missing_epg_path = tmp_path / "does-not-exist.xml"
    result = runner.invoke(
        cli_main.app,
        [
            "report",
            "--skip-streams",
            "--skip-logos",
            "--formats",
            "json",
            "--epg",
            str(missing_epg_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "EPG matching skipped due to an error" in result.output

    reports_dir = isolated_settings.project_root / isolated_settings.reports_dir
    assert (reports_dir / "report.json").exists()
    assert isolated_settings.master_playlist_path.exists()
