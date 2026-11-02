"""Unit tests for application.use_cases.assign_channel_numbers."""

from iptv_manager.application.use_cases.assign_channel_numbers import (
    AssignChannelNumbersUseCase,
)
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.stream_url import StreamUrl


def _channel(name: str) -> Channel:
    return Channel(name=name, url=StreamUrl.parse(f"http://example.com/{name}.m3u8"))


def test_numbers_channels_sequentially_from_one_in_current_order():
    playlist = Playlist(name="t", channels=[_channel("B"), _channel("A"), _channel("C")])
    result = AssignChannelNumbersUseCase().execute(playlist)
    assert [(c.name, c.tvg_chno) for c in result] == [("B", 1), ("A", 2), ("C", 3)]


def test_custom_start_number():
    playlist = Playlist(name="t", channels=[_channel("A"), _channel("B")])
    result = AssignChannelNumbersUseCase().execute(playlist, start=100)
    assert [c.tvg_chno for c in result] == [100, 101]


def test_overwrites_an_upstream_provided_number():
    # This project's own numbering always wins over whatever a source
    # file happened to carry.
    channel = _channel("A").with_tvg_chno(999)
    result = AssignChannelNumbersUseCase().execute(Playlist(name="t", channels=[channel]))
    assert result.channels[0].tvg_chno == 1


def test_does_not_mutate_the_input_playlist():
    playlist = Playlist(name="t", channels=[_channel("A")])
    AssignChannelNumbersUseCase().execute(playlist)
    assert playlist.channels[0].tvg_chno is None


def test_empty_playlist_stays_empty():
    result = AssignChannelNumbersUseCase().execute(Playlist(name="t"))
    assert len(result) == 0


def test_preserves_playlist_epg_url():
    playlist = Playlist(name="t", channels=[_channel("A")], epg_url="http://e.com/epg.xml")
    assert AssignChannelNumbersUseCase().execute(playlist).epg_url == "http://e.com/epg.xml"
