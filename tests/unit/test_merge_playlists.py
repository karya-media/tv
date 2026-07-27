"""Unit tests for application.use_cases.merge_playlists."""

from pathlib import Path

import pytest

from iptv_manager.application.use_cases.merge_playlists import MergePlaylistsUseCase
from iptv_manager.infrastructure.parsers.m3u_parser import M3UParser

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def merged():
    parser = M3UParser()
    sports_raw = FIXTURES.joinpath("sports.m3u").read_text(encoding="utf-8")
    news_raw = FIXTURES.joinpath("news.m3u").read_text(encoding="utf-8-sig")

    sports = parser.parse(sports_raw, name="sports", category="sports")
    news = parser.parse(news_raw, name="news", category="news")

    return MergePlaylistsUseCase().execute([sports, news])


def test_total_channels_before_dedup(merged):
    # sports.m3u: 2 valid entries. news.m3u: 3 valid entries (1 malformed skipped).
    assert merged.total_channels_before == 5


def test_duplicate_url_removed(merged):
    # espn.m3u8 appears in both sports.m3u and news.m3u -> one is dropped.
    assert merged.total_channels_after == 4
    assert merged.removed_duplicate_url_count == 1


def test_duplicate_url_group_records_kept_and_removed(merged):
    assert len(merged.duplicate_urls) == 1
    group = merged.duplicate_urls[0]
    assert group.kept.name == "ESPN HD"  # first-seen (from sports.m3u) wins
    assert len(group.removed) == 1
    assert group.removed[0].name == "ESPN (duplicate URL)"


def test_duplicate_tvg_id_flagged_but_kept(merged):
    # tvg-id "espn.us" is shared by ESPN HD (kept from the URL-dup group)
    # and ESPN Backup Feed (a distinct URL) -> flagged, both kept.
    assert len(merged.duplicate_tvg_ids) == 1
    group = merged.duplicate_tvg_ids[0]
    assert group.tvg_id == "espn.us"
    names = {c.name for c in group.channels}
    assert names == {"ESPN HD", "ESPN Backup Feed"}


def test_non_duplicated_channels_survive(merged):
    names = {c.name for c in merged.master}
    assert "Fox Sports" in names
    assert "CNN" in names


def test_parser_warnings_carried_into_master(merged):
    assert any("malformed #EXTINF" in w for w in merged.master.warnings)


def test_empty_input_produces_empty_master():
    result = MergePlaylistsUseCase().execute([])
    assert result.total_channels_before == 0
    assert result.total_channels_after == 0
    assert result.duplicate_urls == []
    assert result.duplicate_tvg_ids == []
