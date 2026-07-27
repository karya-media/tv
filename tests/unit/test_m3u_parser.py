"""Unit tests for infrastructure.parsers.m3u_parser.M3UParser."""

from pathlib import Path

import pytest

from iptv_manager.infrastructure.parsers.m3u_parser import M3UParser

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def parser() -> M3UParser:
    return M3UParser()


class TestParseBasic:
    def test_parses_all_valid_channels(self, parser: M3UParser):
        raw = FIXTURES.joinpath("sports.m3u").read_text(encoding="utf-8")
        playlist = parser.parse(raw, name="sports", category="sports")

        assert len(playlist) == 2
        assert playlist.channels[0].name == "ESPN HD"
        assert str(playlist.channels[0].tvg_id) == "espn.us"
        assert playlist.channels[0].logo_url == "https://example.com/espn.png"
        assert str(playlist.channels[0].group_title) == "Sports"
        assert str(playlist.channels[0].url) == "http://example.com/stream/espn.m3u8"
        assert playlist.channels[0].source_category == "sports"

    def test_no_warnings_on_clean_file(self, parser: M3UParser):
        raw = FIXTURES.joinpath("sports.m3u").read_text(encoding="utf-8")
        playlist = parser.parse(raw, name="sports")
        assert playlist.warnings == []


class TestParseRepair:
    def test_strips_bom(self, parser: M3UParser):
        raw = FIXTURES.joinpath("news.m3u").read_text(encoding="utf-8-sig")
        playlist = parser.parse(raw, name="news", category="news")
        # If the BOM leaked into parsing, the #EXTM3U header wouldn't
        # be recognized and a spurious warning would be recorded.
        assert not any("missing #EXTM3U header" in w for w in playlist.warnings)

    def test_malformed_extinf_skipped_with_warning(self, parser: M3UParser):
        raw = FIXTURES.joinpath("news.m3u").read_text(encoding="utf-8-sig")
        playlist = parser.parse(raw, name="news", category="news")

        names = [c.name for c in playlist]
        assert "http://example.com/stream/broken.m3u8" not in [str(c.url) for c in playlist]
        assert any("malformed #EXTINF" in w for w in playlist.warnings)
        # The three well-formed entries should still have parsed fine.
        assert len(playlist) == 3
        assert "CNN" in names

    def test_missing_header_recorded_as_warning(self, parser: M3UParser):
        raw = (
            '#EXTINF:-1 tvg-id="x" group-title="Y",Z\n'
            "http://example.com/stream/z.m3u8\n"
        )
        playlist = parser.parse(raw, name="no-header")
        assert len(playlist) == 1
        assert any("missing #EXTM3U header" in w for w in playlist.warnings)

    def test_url_with_no_preceding_extinf_skipped(self, parser: M3UParser):
        raw = "#EXTM3U\nhttp://example.com/orphan.m3u8\n"
        playlist = parser.parse(raw, name="orphan")
        assert len(playlist) == 0
        assert any("no preceding #EXTINF" in w for w in playlist.warnings)

    def test_invalid_stream_url_skipped_with_warning(self, parser: M3UParser):
        raw = (
            "#EXTM3U\n"
            '#EXTINF:-1 group-title="Y",Bad URL Channel\n'
            "not-a-valid-url\n"
        )
        playlist = parser.parse(raw, name="bad-url")
        assert len(playlist) == 0
        assert any("invalid stream URL" in w for w in playlist.warnings)

    def test_unknown_attrs_preserved_in_extra_attrs(self, parser: M3UParser):
        raw = (
            "#EXTM3U\n"
            '#EXTINF:-1 tvg-id="x" tvg-country="US" tvg-language="English" group-title="Y",Z\n'
            "http://example.com/z.m3u8\n"
        )
        playlist = parser.parse(raw, name="extra")
        channel = playlist.channels[0]
        assert channel.extra_attrs == {"tvg-country": "US", "tvg-language": "English"}


class TestSerialize:
    def test_round_trip_preserves_channel_count(self, parser: M3UParser):
        raw = FIXTURES.joinpath("sports.m3u").read_text(encoding="utf-8")
        playlist = parser.parse(raw, name="sports")
        serialized = parser.serialize(playlist)
        reparsed = parser.parse(serialized, name="sports")
        assert len(reparsed) == len(playlist)

    def test_serialize_starts_with_header(self, parser: M3UParser):
        raw = FIXTURES.joinpath("sports.m3u").read_text(encoding="utf-8")
        playlist = parser.parse(raw, name="sports")
        assert parser.serialize(playlist).startswith("#EXTM3U\n")

    def test_serialize_preserves_extra_attrs(self, parser: M3UParser):
        raw = (
            "#EXTM3U\n"
            '#EXTINF:-1 tvg-id="x" tvg-country="US" group-title="Y",Z\n'
            "http://example.com/z.m3u8\n"
        )
        playlist = parser.parse(raw, name="extra")
        serialized = parser.serialize(playlist)
        assert 'tvg-country="US"' in serialized
