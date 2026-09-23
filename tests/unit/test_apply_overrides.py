"""Unit tests for application.use_cases.apply_overrides."""

from iptv_manager.application.use_cases.apply_overrides import ApplyOverridesUseCase
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.channel_override import ChannelOverride
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.group_title import GroupTitle
from iptv_manager.domain.value_objects.stream_url import StreamUrl
from iptv_manager.domain.value_objects.tvg_id import TvgId


def _channel(url: str, tvg_id: str | None = None, group_title: str | None = None) -> Channel:
    return Channel(
        name="X",
        url=StreamUrl.parse(url),
        tvg_id=TvgId.parse(tvg_id),
        group_title=GroupTitle.parse(group_title),
    )


def _run(overrides: list[ChannelOverride], *channels: Channel) -> Playlist:
    playlist = Playlist(name="test", channels=list(channels))
    return ApplyOverridesUseCase().execute(playlist, overrides)


def test_overrides_tvg_id_when_specified():
    result = _run(
        [ChannelOverride(url="http://x.com/1.m3u8", new_tvg_id="RCTI.id")],
        _channel("http://x.com/1.m3u8", tvg_id="TV9.in"),
    )
    assert str(result.channels[0].tvg_id) == "RCTI.id"


def test_overrides_group_title_when_specified():
    result = _run(
        [ChannelOverride(url="http://x.com/1.m3u8", new_group_title="Indonesia;Lokal")],
        _channel("http://x.com/1.m3u8", group_title="India;News"),
    )
    assert str(result.channels[0].group_title) == "Indonesia;Lokal"


def test_overrides_both_fields_at_once():
    result = _run(
        [
            ChannelOverride(
                url="http://x.com/1.m3u8",
                new_tvg_id="TV9.id",
                new_group_title="Indonesia;Lokal",
            )
        ],
        _channel("http://x.com/1.m3u8", tvg_id="TV9.in", group_title="India;News"),
    )
    assert str(result.channels[0].tvg_id) == "TV9.id"
    assert str(result.channels[0].group_title) == "Indonesia;Lokal"


def test_channel_with_no_matching_url_is_untouched():
    result = _run(
        [ChannelOverride(url="http://other.com/x.m3u8", new_tvg_id="RCTI.id")],
        _channel("http://x.com/1.m3u8", tvg_id="Original.id"),
    )
    assert str(result.channels[0].tvg_id) == "Original.id"


def test_empty_override_row_is_a_no_op():
    result = _run(
        [ChannelOverride(url="http://x.com/1.m3u8")],
        _channel("http://x.com/1.m3u8", tvg_id="Original.id"),
    )
    assert str(result.channels[0].tvg_id) == "Original.id"


def test_only_new_tvg_id_filled_leaves_group_title_untouched():
    result = _run(
        [ChannelOverride(url="http://x.com/1.m3u8", new_tvg_id="RCTI.id")],
        _channel("http://x.com/1.m3u8", tvg_id="Old.id", group_title="India;News"),
    )
    assert str(result.channels[0].group_title) == "India;News"


def test_no_overrides_at_all_returns_playlist_unchanged():
    playlist = Playlist(
        name="test", channels=[_channel("http://x.com/1.m3u8", tvg_id="Original.id")]
    )
    result = ApplyOverridesUseCase().execute(playlist, [])
    assert result is playlist
