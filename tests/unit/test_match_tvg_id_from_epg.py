"""Unit tests for application.use_cases.match_tvg_id_from_epg."""

from iptv_manager.application.use_cases.match_tvg_id_from_epg import (
    MatchTvgIdFromEpgUseCase,
)
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.epg_channel import EPGChannel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.stream_url import StreamUrl
from iptv_manager.domain.value_objects.tvg_id import TvgId


def _channel(name: str, tvg_id: str | None = None) -> Channel:
    return Channel(
        name=name,
        url=StreamUrl.parse(f"http://example.com/{name}.m3u8"),
        tvg_id=TvgId.parse(tvg_id),
    )


def _run(epg_channels: list[EPGChannel], *channels: Channel) -> Playlist:
    playlist = Playlist(name="test", channels=list(channels))
    return MatchTvgIdFromEpgUseCase().execute(playlist, epg_channels)


def test_fills_missing_tvg_id_from_exact_epg_display_name_match():
    epg = [EPGChannel(id="rt.uk", display_names=("Russia Today",))]
    result = _run(epg, _channel("Russia Today"))
    assert str(result.channels[0].tvg_id) == "rt.uk"


def test_matches_case_and_whitespace_insensitively():
    epg = [EPGChannel(id="rt.uk", display_names=("Russia Today",))]
    result = _run(epg, _channel("  russia today  "))
    assert str(result.channels[0].tvg_id) == "rt.uk"


def test_matches_any_of_an_epg_channels_alternate_display_names():
    epg = [EPGChannel(id="rt.uk", display_names=("RT", "Russia Today"))]
    result = _run(epg, _channel("RT"))
    assert str(result.channels[0].tvg_id) == "rt.uk"


def test_does_not_touch_a_different_variant_name():
    epg = [EPGChannel(id="rt.uk", display_names=("Russia Today",))]
    result = _run(epg, _channel("Russia Today 2"))
    assert str(result.channels[0].tvg_id) == ""


def test_does_not_overwrite_an_existing_tvg_id():
    epg = [EPGChannel(id="rt.uk", display_names=("Russia Today",))]
    result = _run(epg, _channel("Russia Today", tvg_id="AlreadySet.us"))
    assert str(result.channels[0].tvg_id) == "AlreadySet.us"


def test_ambiguous_name_across_multiple_epg_channels_is_skipped():
    epg = [
        EPGChannel(id="a.us", display_names=("Movie Channel",)),
        EPGChannel(id="b.uk", display_names=("Movie Channel",)),
    ]
    result = _run(epg, _channel("Movie Channel"))
    assert str(result.channels[0].tvg_id) == ""


def test_name_with_no_match_in_epg_is_left_alone():
    epg = [EPGChannel(id="rt.uk", display_names=("Russia Today",))]
    result = _run(epg, _channel("Some Other Channel"))
    assert str(result.channels[0].tvg_id) == ""


def test_empty_epg_list_leaves_everything_unchanged():
    result = _run([], _channel("Russia Today"))
    assert str(result.channels[0].tvg_id) == ""
