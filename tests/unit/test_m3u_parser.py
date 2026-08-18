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

    def test_html_entities_in_url_are_unescaped(self, parser: M3UParser):
        # Real-world bug found in a user-supplied playlist export: the
        # URL's query string had "&amp;" instead of "&", which silently
        # breaks every parameter after the first when a player uses it
        # literally instead of HTML-decoding it first.
        raw = (
            "#EXTM3U\n"
            '#EXTINF:-1 group-title="Y",tvOne\n'
            "https://example.com/01.m3u8?app_type=web&amp;userid=abc&amp;chname=tvOne\n"
        )
        playlist = parser.parse(raw, name="entities")
        assert str(playlist.channels[0].url) == (
            "https://example.com/01.m3u8?app_type=web&userid=abc&chname=tvOne"
        )

    def test_html_entities_in_extinf_attrs_are_unescaped(self, parser: M3UParser):
        raw = (
            "#EXTM3U\n"
            '#EXTINF:-1 tvg-name="AT&amp;T Sports" group-title="Y",AT&amp;T Sports\n'
            "http://example.com/z.m3u8\n"
        )
        playlist = parser.parse(raw, name="entities")
        channel = playlist.channels[0]
        assert channel.tvg_name == "AT&T Sports"
        assert channel.name == "AT&T Sports"

    def test_html_entities_in_vlcopt_are_unescaped(self, parser: M3UParser):
        raw = (
            "#EXTM3U\n"
            '#EXTINF:-1 group-title="Y",Z\n'
            "#EXTVLCOPT:http-referrer=https://example.com/watch?id=1&amp;ref=2\n"
            "http://example.com/z.m3u8\n"
        )
        playlist = parser.parse(raw, name="entities")
        channel = playlist.channels[0]
        assert channel.vlc_opts["http-referrer"] == "https://example.com/watch?id=1&ref=2"

    def test_duplicate_url_detected_after_html_unescape(self, parser: M3UParser):
        # Two entries that are the *same* stream once entities are
        # decoded must produce the same normalized_key, so merge-time
        # dedup catches them - this was the actual user-visible symptom
        # of the bug (tvOne appeared twice in the merged master.m3u).
        clean = (
            "#EXTM3U\n"
            '#EXTINF:-1 group-title="Y",tvOne\n'
            "https://example.com/01.m3u8?app_type=web&userid=abc&chname=tvOne\n"
        )
        escaped = (
            "#EXTM3U\n"
            '#EXTINF:-1 group-title="Y",tvOne\n'
            "https://example.com/01.m3u8?app_type=web&amp;userid=abc&amp;chname=tvOne\n"
        )
        channel_a = parser.parse(clean, name="a").channels[0]
        channel_b = parser.parse(escaped, name="b").channels[0]
        assert channel_a.url.normalized_key == channel_b.url.normalized_key


class TestVlcOpts:
    def test_vlc_opts_captured_on_channel(self, parser: M3UParser):
        raw = (
            "#EXTM3U\n"
            '#EXTINF:-1 group-title="Y",Z\n'
            "#EXTVLCOPT:http-user-agent=Mozilla/5.0\n"
            "#EXTVLCOPT:http-referrer=https://example.com/\n"
            "http://example.com/z.m3u8\n"
        )
        playlist = parser.parse(raw, name="vlc")
        channel = playlist.channels[0]
        assert channel.vlc_opts == {
            "http-user-agent": "Mozilla/5.0",
            "http-referrer": "https://example.com/",
        }

    def test_vlc_opts_default_empty_when_absent(self, parser: M3UParser):
        raw = "#EXTM3U\n" '#EXTINF:-1 group-title="Y",Z\n' "http://example.com/z.m3u8\n"
        playlist = parser.parse(raw, name="no-vlc")
        assert playlist.channels[0].vlc_opts == {}

    def test_vlc_opt_with_no_preceding_extinf_warns(self, parser: M3UParser):
        raw = "#EXTM3U\n#EXTVLCOPT:http-user-agent=Mozilla/5.0\nhttp://example.com/z.m3u8\n"
        playlist = parser.parse(raw, name="orphan-vlc")
        assert any("EXTVLCOPT" in w for w in playlist.warnings)
        # The URL after the orphan EXTVLCOPT still has no preceding
        # #EXTINF either, so it's skipped too - zero channels parsed.
        assert len(playlist) == 0

    def test_vlc_opts_do_not_leak_between_channels(self, parser: M3UParser):
        raw = (
            "#EXTM3U\n"
            '#EXTINF:-1 group-title="Y",First\n'
            "#EXTVLCOPT:http-user-agent=Agent1\n"
            "http://example.com/first.m3u8\n"
            '#EXTINF:-1 group-title="Y",Second\n'
            "http://example.com/second.m3u8\n"
        )
        playlist = parser.parse(raw, name="no-leak")
        assert playlist.channels[0].vlc_opts == {"http-user-agent": "Agent1"}
        assert playlist.channels[1].vlc_opts == {}

    def test_vlc_opts_round_trip_through_serialize(self, parser: M3UParser):
        raw = (
            "#EXTM3U\n"
            '#EXTINF:-1 group-title="Y",Z\n'
            "#EXTVLCOPT:http-user-agent=Mozilla/5.0\n"
            "http://example.com/z.m3u8\n"
        )
        playlist = parser.parse(raw, name="vlc")
        serialized = parser.serialize(playlist)
        assert "#EXTVLCOPT:http-user-agent=Mozilla/5.0" in serialized

        reparsed = parser.parse(serialized, name="vlc")
        assert reparsed.channels[0].vlc_opts == {"http-user-agent": "Mozilla/5.0"}


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

    def test_serialize_without_epg_url_omits_url_tvg(self, parser: M3UParser):
        raw = FIXTURES.joinpath("sports.m3u").read_text(encoding="utf-8")
        playlist = parser.parse(raw, name="sports")
        assert parser.serialize(playlist).startswith("#EXTM3U\n")

    def test_serialize_with_epg_url_adds_url_tvg_header(self, parser: M3UParser):
        raw = FIXTURES.joinpath("sports.m3u").read_text(encoding="utf-8")
        playlist = parser.parse(raw, name="sports")
        serialized = parser.serialize(playlist, epg_url="https://example.com/epg.xml.gz")
        assert serialized.startswith('#EXTM3U url-tvg="https://example.com/epg.xml.gz"\n')

    def test_epg_url_header_round_trips_through_parse(self, parser: M3UParser):
        raw = FIXTURES.joinpath("sports.m3u").read_text(encoding="utf-8")
        playlist = parser.parse(raw, name="sports")
        serialized = parser.serialize(playlist, epg_url="https://example.com/epg.xml.gz")
        reparsed = parser.parse(serialized, name="sports")
        assert len(reparsed) == len(playlist)
