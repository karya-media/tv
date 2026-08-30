"""Integration test: the `iptv-manager merge` CLI command end-to-end,
against real files on disk (in a temp directory), exercising the full
stack: settings -> CLI -> parser -> merge use case -> file output.
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


class TestPlaylistBundles:
    def test_playlists_txt_publishes_multiple_named_bundles(self, isolated_settings: Settings):
        (isolated_settings.project_root / "data" / "playlists.txt").write_text(
            "everything=sports,news\nsports_only=sports\n", encoding="utf-8"
        )

        result = runner.invoke(cli_main.app, ["merge"])

        assert result.exit_code == 0, result.output
        everything_path = isolated_settings.master_path / "everything.m3u"
        sports_only_path = isolated_settings.master_path / "sports_only.m3u"
        assert everything_path.exists()
        assert sports_only_path.exists()
        assert sports_only_path.read_text(encoding="utf-8").count("#EXTINF") == 1
        assert everything_path.read_text(encoding="utf-8").count("#EXTINF") == 2

    def test_warns_about_a_bundle_referencing_an_unknown_category(
        self, isolated_settings: Settings
    ):
        (isolated_settings.project_root / "data" / "playlists.txt").write_text(
            "master=sports,does_not_exist\n", encoding="utf-8"
        )

        result = runner.invoke(cli_main.app, ["merge"])

        assert result.exit_code == 0, result.output
        assert "does_not_exist" in result.output
        assert "unknown" in result.output

    def test_warns_about_a_category_not_referenced_by_any_bundle(
        self, isolated_settings: Settings
    ):
        # A category with URLs that don't overlap anything else, so
        # it can only become "covered" via an explicit bundle - unlike
        # the shared NEWS_M3U/SPORTS_M3U fixtures, which deliberately
        # share one duplicate URL for the dedup tests elsewhere in
        # this file.
        (isolated_settings.categories_path / "weather.m3u").write_text(
            "#EXTM3U\n"
            '#EXTINF:-1 group-title="Weather",Weather Channel\n'
            "http://example.com/stream/weather-unique.m3u8\n",
            encoding="utf-8",
        )
        (isolated_settings.project_root / "data" / "playlists.txt").write_text(
            "master=sports\n", encoding="utf-8"
        )

        result = runner.invoke(cli_main.app, ["merge"])

        assert result.exit_code == 0, result.output
        assert "weather" in result.output
        assert "playlists.txt bundle" in result.output

    def test_no_playlists_txt_falls_back_to_a_single_master_bundle(
        self, isolated_settings: Settings
    ):
        result = runner.invoke(cli_main.app, ["merge"])

        assert result.exit_code == 0, result.output
        assert isolated_settings.master_playlist_path.exists()
        assert not (isolated_settings.master_path / "sports_only.m3u").exists()

    def test_group_prefix_bundle_selects_channels_by_group_title_across_files(
        self, isolated_settings: Settings
    ):
        # "News" channels come from a different category file than
        # "Sports", but a group: bundle must pull them together purely
        # by group-title, regardless of source file. No tvg-id here on
        # purpose - CategorizeByCountryUseCase leaves group-title
        # completely untouched for a channel with no tvg-id, keeping
        # this test's expectations simple and unambiguous.
        (isolated_settings.categories_path / "custom_sports.m3u").write_text(
            '#EXTM3U\n#EXTINF:-1 group-title="Sports",Custom Sports Channel\n'
            "http://example.com/stream/custom-sports.m3u8\n",
            encoding="utf-8",
        )
        (isolated_settings.categories_path / "custom_news.m3u").write_text(
            '#EXTM3U\n#EXTINF:-1 group-title="News",Custom News Channel\n'
            "http://example.com/stream/custom-news.m3u8\n",
            encoding="utf-8",
        )
        (isolated_settings.project_root / "data" / "playlists.txt").write_text(
            "news_only=group:News\n", encoding="utf-8"
        )

        result = runner.invoke(cli_main.app, ["merge"])

        assert result.exit_code == 0, result.output
        news_only_path = isolated_settings.master_path / "news_only.m3u"
        assert news_only_path.exists()
        news_text = news_only_path.read_text(encoding="utf-8")
        assert "Custom News Channel" in news_text
        assert "Custom Sports Channel" not in news_text

    def test_stem_and_group_prefix_can_be_combined_without_duplicating_channels(
        self, isolated_settings: Settings
    ):
        (isolated_settings.categories_path / "custom_news.m3u").write_text(
            '#EXTM3U\n#EXTINF:-1 group-title="News",Custom News Channel\n'
            "http://example.com/stream/custom-news.m3u8\n",
            encoding="utf-8",
        )
        (isolated_settings.project_root / "data" / "playlists.txt").write_text(
            "combined=sports,group:News\n", encoding="utf-8"
        )

        result = runner.invoke(cli_main.app, ["merge"])

        assert result.exit_code == 0, result.output
        combined_path = isolated_settings.master_path / "combined.m3u"
        combined_text = combined_path.read_text(encoding="utf-8")
        # sports.m3u's ESPN (via stem) + the custom News channel (via
        # group: prefix) - two distinct channels, no duplication.
        assert combined_text.count("#EXTINF") == 2
        assert "ESPN" in combined_text
        assert "Custom News Channel" in combined_text

    def test_group_prefix_matching_no_channels_warns_and_skips(
        self, isolated_settings: Settings
    ):
        (isolated_settings.project_root / "data" / "playlists.txt").write_text(
            "empty_bundle=group:NoSuchCountry\n", encoding="utf-8"
        )

        result = runner.invoke(cli_main.app, ["merge"])

        assert result.exit_code == 0, result.output
        assert not (isolated_settings.master_path / "empty_bundle.m3u").exists()
        assert "matched no channels" in result.output

    def test_wildcard_bundle_includes_every_category_automatically(
        self, isolated_settings: Settings
    ):
        # A brand-new category file, never mentioned in playlists.txt,
        # must still show up in a "*" bundle - that's the whole point:
        # no manual update needed when a new source appears.
        (isolated_settings.categories_path / "brand_new_source.m3u").write_text(
            '#EXTM3U\n#EXTINF:-1 group-title="Other",Brand New Channel\n'
            "http://example.com/stream/brand-new.m3u8\n",
            encoding="utf-8",
        )
        (isolated_settings.project_root / "data" / "playlists.txt").write_text(
            "everything=*\n", encoding="utf-8"
        )

        result = runner.invoke(cli_main.app, ["merge"])

        assert result.exit_code == 0, result.output
        everything_path = isolated_settings.master_path / "everything.m3u"
        assert everything_path.exists()
        assert "Brand New Channel" in everything_path.read_text(encoding="utf-8")
        # A wildcard bundle covers every category by definition - no
        # orphan warning should ever fire alongside it.
        assert "playlists.txt bundle" not in result.output
