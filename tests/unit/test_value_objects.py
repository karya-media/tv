"""Unit tests for domain value objects."""

import pytest

from iptv_manager.domain.value_objects.group_title import DEFAULT_GROUP, GroupTitle
from iptv_manager.domain.value_objects.stream_url import InvalidStreamUrlError, StreamUrl
from iptv_manager.domain.value_objects.tvg_id import TvgId


class TestTvgId:
    def test_none_is_empty(self):
        assert TvgId.parse(None) is TvgId.EMPTY
        assert not TvgId.parse(None).is_present

    def test_blank_string_is_empty(self):
        assert TvgId.parse("   ") is TvgId.EMPTY

    def test_valid_id_preserved(self):
        tvg_id = TvgId.parse("espn.us")
        assert str(tvg_id) == "espn.us"
        assert tvg_id.is_present

    def test_invalid_characters_are_stripped_not_rejected(self):
        tvg_id = TvgId.parse("espn us!!")
        assert str(tvg_id) == "espnus"

    def test_whitespace_trimmed(self):
        assert str(TvgId.parse("  cnn.us  ")) == "cnn.us"


class TestStreamUrl:
    def test_valid_http_url(self):
        url = StreamUrl.parse("http://example.com/stream.m3u8")
        assert url.scheme == "http"
        assert url.host == "example.com"

    def test_valid_rtmp_url(self):
        url = StreamUrl.parse("rtmp://example.com/live/stream")
        assert url.scheme == "rtmp"

    def test_missing_scheme_rejected(self):
        with pytest.raises(InvalidStreamUrlError):
            StreamUrl.parse("example.com/stream.m3u8")

    def test_unsupported_scheme_rejected(self):
        with pytest.raises(InvalidStreamUrlError):
            StreamUrl.parse("ftp://example.com/stream.m3u8")

    def test_empty_rejected(self):
        with pytest.raises(InvalidStreamUrlError):
            StreamUrl.parse("   ")

    def test_none_rejected(self):
        with pytest.raises(InvalidStreamUrlError):
            StreamUrl.parse(None)

    def test_normalized_key_is_case_and_slash_insensitive(self):
        a = StreamUrl.parse("HTTP://Example.com/stream/")
        b = StreamUrl.parse("http://example.com/stream")
        assert a.normalized_key == b.normalized_key


class TestGroupTitle:
    def test_none_uses_default(self):
        assert str(GroupTitle.parse(None)) == DEFAULT_GROUP

    def test_blank_uses_default(self):
        assert str(GroupTitle.parse("   ")) == DEFAULT_GROUP

    def test_collapses_internal_whitespace(self):
        assert str(GroupTitle.parse("  Sports   HD  ")) == "Sports HD"

    def test_strips_emoji_prefix(self):
        assert str(GroupTitle.parse("📺 Nasional")) == "Nasional"
        assert str(GroupTitle.parse("🔓 Dens TV")) == "Dens TV"
        assert str(GroupTitle.parse("🔭 CCTV")) == "CCTV"

    def test_dedupes_repeated_segments(self):
        assert (
            str(GroupTitle.parse("Indonesia;Lainnya;Lainnya"))
            == "Indonesia;Lainnya"
        )

    def test_placeholder_labels_use_default(self):
        assert str(GroupTitle.parse("Undefined")) == DEFAULT_GROUP
        assert str(GroupTitle.parse("General")) == DEFAULT_GROUP
        assert str(GroupTitle.parse("undefined")) == DEFAULT_GROUP

    def test_preserves_meaningful_multi_segment_title(self):
        assert (
            str(GroupTitle.parse("Indonesia;Nasional"))
            == "Indonesia;Nasional"
        )
