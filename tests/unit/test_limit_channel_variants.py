"""Unit tests for application.use_cases.limit_channel_variants."""

from iptv_manager.application.use_cases.limit_channel_variants import (
    LimitChannelVariantsUseCase,
    online_urls_from_results,
)
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.entities.stream_validation_result import (
    StreamStatus,
    StreamValidationResult,
)
from iptv_manager.domain.value_objects.stream_url import StreamUrl
from iptv_manager.domain.value_objects.tvg_id import TvgId


def _channel(name: str, url: str, tvg_id: str | None = None) -> Channel:
    return Channel(name=name, url=StreamUrl.parse(url), tvg_id=TvgId.parse(tvg_id))


def _names(playlist: Playlist) -> list[str]:
    return [c.name for c in playlist]


def _run(
    priority_slots: list[list[str]],
    channels: list[Channel],
    online_urls: set[str] | None = None,
    max_variants: int = 2,
) -> Playlist:
    playlist = Playlist(name="test", channels=channels)
    return LimitChannelVariantsUseCase().execute(
        priority_slots, playlist, online_urls=online_urls, max_variants=max_variants
    )


class TestLimitChannelVariants:
    def test_no_priority_slots_returns_playlist_unchanged(self):
        result = _run([], [_channel("A", "http://x.com/a.m3u8")])
        assert _names(result) == ["A"]

    def test_group_at_or_under_the_cap_is_left_untouched(self):
        channels = [
            _channel("RCTI", "http://a.com/1.m3u8"),
            _channel("RCTI HD", "http://a.com/2.m3u8"),
        ]
        result = _run([["RCTI", "RCTI HD"]], channels)
        assert _names(result) == ["RCTI", "RCTI HD"]

    def test_prefers_online_variants_when_over_the_cap(self):
        channels = [
            _channel("RCTI", "http://a.com/1.m3u8"),
            _channel("RCTI HD", "http://a.com/2.m3u8"),
            _channel("RCTI 2", "http://a.com/3.m3u8"),
        ]
        online = {"http://a.com/1.m3u8", "http://a.com/3.m3u8"}
        result = _run([["RCTI", "RCTI HD", "RCTI 2"]], channels, online_urls=online)
        assert set(_names(result)) == {"RCTI", "RCTI 2"}

    def test_falls_back_to_non_online_variants_to_fill_the_cap(self):
        # Only one variant confirmed online - still keep 2 total by
        # filling the rest of the cap with not-yet-confirmed ones,
        # rather than dropping down to a single channel.
        channels = [
            _channel("RCTI", "http://a.com/1.m3u8"),
            _channel("RCTI HD", "http://a.com/2.m3u8"),
            _channel("RCTI 2", "http://a.com/3.m3u8"),
        ]
        online = {"http://a.com/2.m3u8"}
        result = _run([["RCTI", "RCTI HD", "RCTI 2"]], channels, online_urls=online)
        assert len(result) == 2
        assert "RCTI HD" in _names(result)

    def test_none_online_urls_keeps_first_n_in_original_order(self):
        channels = [
            _channel("RCTI 2", "http://a.com/3.m3u8"),
            _channel("RCTI", "http://a.com/1.m3u8"),
            _channel("RCTI HD", "http://a.com/2.m3u8"),
        ]
        result = _run([["RCTI", "RCTI HD", "RCTI 2"]], channels, online_urls=None)
        assert _names(result) == ["RCTI 2", "RCTI"]

    def test_channels_outside_any_slot_are_never_dropped(self):
        channels = [
            _channel("RCTI", "http://a.com/1.m3u8"),
            _channel("RCTI HD", "http://a.com/2.m3u8"),
            _channel("RCTI 2", "http://a.com/3.m3u8"),
            _channel("Some Other Channel", "http://a.com/4.m3u8"),
        ]
        result = _run([["RCTI", "RCTI HD", "RCTI 2"]], channels, online_urls=None)
        assert "Some Other Channel" in _names(result)
        assert len(result) == 3

    def test_foreign_channel_never_counted_against_a_different_countrys_cap(self):
        # Country guard (shared with ApplyChannelOrderUseCase) keeps
        # India's "INews (720p)" out of Indonesia's "iNews" family
        # entirely - it must never even count toward the cap, let
        # alone be dropped by it.
        channels = [
            _channel("iNews", "http://a.com/1.m3u8", tvg_id="iNews.id"),
            _channel("INews (720p)", "http://a.com/2.m3u8", tvg_id="INews.inSD"),
        ]
        result = _run([["iNews"]], channels, online_urls=None)
        assert set(_names(result)) == {"iNews", "INews (720p)"}

    def test_max_variants_of_zero_or_negative_returns_playlist_unchanged(self):
        channels = [
            _channel("RCTI", "http://a.com/1.m3u8"),
            _channel("RCTI HD", "http://a.com/2.m3u8"),
        ]
        result = _run([["RCTI", "RCTI HD"]], channels, max_variants=0)
        assert _names(result) == ["RCTI", "RCTI HD"]


class TestOnlineUrlsFromResults:
    def test_extracts_only_online_channel_urls(self):
        online_channel = _channel("A", "http://a.com/1.m3u8")
        offline_channel = _channel("B", "http://a.com/2.m3u8")
        results = [
            StreamValidationResult(channel=online_channel, status=StreamStatus.ONLINE),
            StreamValidationResult(channel=offline_channel, status=StreamStatus.OFFLINE),
        ]
        assert online_urls_from_results(results) == {"http://a.com/1.m3u8"}
