"""Integration test: the `iptv-manager merge` CLI command end-to-end,
against real files on disk (in a temp directory), exercising the full
stack: settings -> CLI -> parser -> merge use case -> file output.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from iptv_manager.config.settings import Settings, get_settings
import iptv_manager.interfaces.cli.main as cli_main

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
    '#EXTINF:-1 tvg-id="espn.us" group-title="Sports",ESPN Duplicate\n'
    "http://example.com/stream/espn.m3u8\n"  # duplicate URL of the sports entry
)


@pytest.fixture
def isolated_settings(tmp_path: Path, monkeypatch):
    """Point the CLI at a throwaway project root instead of the real repo."""
    get_settings.cache_clear()

    settings = Settings(
        project_root=tmp_path,
        github_repository=None,
    )
    settings.ensure_directories()
    (settings.categories_path / "sports.m3u").write_text(SPORTS_M3U, encoding="utf-8")
    (settings.categories_path / "news.m3u").write_text(NEWS_M3U, encoding="utf-8")

    monkeypatch.setattr(cli_main, "get_settings", lambda: settings)
    yield settings
    get_settings.cache_clear()


def test_merge_command_writes_master_playlist(isolated_settings: Settings):
    result = runner.invoke(cli_main.app, ["merge"])

    assert result.exit_code == 0, result.output
    assert isolated_settings.master_playlist_path.exists()

    master_text = isolated_settings.master_playlist_path.read_text(encoding="utf-8")
    assert master_text.startswith("#EXTM3U")
    assert master_text.count("#EXTINF") == 2  # duplicate URL removed


def test_merge_command_reports_duplicate_url_removed(isolated_settings: Settings):
    result = runner.invoke(cli_main.app, ["merge"])
    assert "Duplicate URLs removed: 1" in result.output


def test_merge_command_also_writes_docs_copy_when_publish_target_is_both(
    isolated_settings: Settings,
):
    assert isolated_settings.publish_target.value == "both"
    runner.invoke(cli_main.app, ["merge"])
    assert isolated_settings.docs_master_playlist_path.exists()


def test_merge_command_fails_cleanly_with_no_category_files(tmp_path: Path, monkeypatch):
    get_settings.cache_clear()
    settings = Settings(project_root=tmp_path, github_repository=None)
    settings.ensure_directories()
    monkeypatch.setattr(cli_main, "get_settings", lambda: settings)

    result = runner.invoke(cli_main.app, ["merge"])

    assert result.exit_code == 1
    get_settings.cache_clear()
