"""Unit tests for application.use_cases.backfill_tvg_id."""

from iptv_manager.application.use_cases.backfill_tvg_id import (
    BackfillTvgIdFromExactNameUseCase,
)
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.stream_url import StreamUrl
from iptv_manager.domain.value_objects.tvg_id import TvgId


def _channel(name: str, url: str, tvg_id: str | None = None) -> Channel:
    return Channel(name=name, url=StreamUrl.parse(url), tvg_id=TvgId.parse(tvg_id))


def _run(*channels: Channel) -> Playlist:
    playlist = Playlist(name="test", channels=list(channels))
    return BackfillTvgIdFromExactNameUseCase().execute(playlist)


def test_fills_missing_tvg_id_from_exact_name_match():
    result = _run(
        _channel("RCTI", "http://a.com/rcti1.m3u8", "RCTI.id"),
        _channel("RCTI", "http://b.com/rcti2.m3u8", None),
    )
    assert [str(c.tvg_id) for c in result] == ["RCTI.id", "RCTI.id"]


def test_matches_case_and_whitespace_insensitively():
    result = _run(
        _channel("RCTI", "http://a.com/1.m3u8", "RCTI.id"),
        _channel("  rcti  ", "http://b.com/2.m3u8", None),
    )
    assert str(result.channels[1].tvg_id) == "RCTI.id"


def test_does_not_touch_a_different_variant_name():
    result = _run(
        _channel("RCTI", "http://a.com/1.m3u8", "RCTI.id"),
        _channel("RCTI 2", "http://b.com/2.m3u8", None),
    )
    assert str(result.channels[1].tvg_id) == ""


def test_does_not_overwrite_an_existing_tvg_id():
    result = _run(
        _channel("RCTI", "http://a.com/1.m3u8", "RCTI.id"),
        _channel("RCTI", "http://b.com/2.m3u8", "SomethingElse.id"),
    )
    assert str(result.channels[1].tvg_id) == "SomethingElse.id"


def test_conflicting_tvg_ids_for_the_same_name_are_left_alone():
    result = _run(
        _channel("Foo", "http://a.com/1.m3u8", "Foo.id"),
        _channel("Foo", "http://b.com/2.m3u8", "Foo.us"),
        _channel("Foo", "http://c.com/3.m3u8", None),
    )
    assert str(result.channels[2].tvg_id) == ""


def test_name_with_no_match_anywhere_is_left_alone():
    result = _run(_channel("Mystery Channel", "http://a.com/1.m3u8", None))
    assert str(result.channels[0].tvg_id) == ""
