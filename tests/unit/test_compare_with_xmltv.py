"""Unit tests for application.use_cases.compare_with_xmltv."""

from iptv_manager.application.use_cases.compare_with_xmltv import CompareWithXMLTVUseCase
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.epg_channel import EPGChannel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.group_title import GroupTitle
from iptv_manager.domain.value_objects.stream_url import StreamUrl
from iptv_manager.domain.value_objects.tvg_id import TvgId


def _channel(name: str, url: str, tvg_id: str | None) -> Channel:
    return Channel(
        name=name,
        url=StreamUrl.parse(url),
        tvg_id=TvgId.parse(tvg_id),
        group_title=GroupTitle.parse("Test"),
    )


def test_missing_tvg_id_detected():
    playlist = Playlist(name="p", channels=[_channel("No ID", "http://x.com/a", None)])
    result = CompareWithXMLTVUseCase().execute(playlist, [])
    assert len(result.missing_tvg_id) == 1
    assert result.missing_tvg_id[0].name == "No ID"


def test_invalid_tvg_id_detected_when_not_in_epg():
    playlist = Playlist(
        name="p", channels=[_channel("Ghost Channel", "http://x.com/a", "does.not.exist")]
    )
    epg = [EPGChannel(id="espn.us", display_names=("ESPN",))]
    result = CompareWithXMLTVUseCase().execute(playlist, epg)
    assert len(result.invalid_tvg_id) == 1
    assert result.invalid_tvg_id[0].name == "Ghost Channel"


def test_matching_tvg_id_is_neither_missing_nor_invalid():
    playlist = Playlist(name="p", channels=[_channel("ESPN", "http://x.com/a", "espn.us")])
    epg = [EPGChannel(id="espn.us", display_names=("ESPN",))]
    result = CompareWithXMLTVUseCase().execute(playlist, epg)
    assert result.missing_tvg_id == []
    assert result.invalid_tvg_id == []


def test_duplicate_tvg_id_within_playlist_detected():
    playlist = Playlist(
        name="p",
        channels=[
            _channel("ESPN Primary", "http://x.com/a", "espn.us"),
            _channel("ESPN Backup", "http://x.com/b", "espn.us"),
        ],
    )
    epg = [EPGChannel(id="espn.us", display_names=("ESPN",))]
    result = CompareWithXMLTVUseCase().execute(playlist, epg)
    assert len(result.duplicate_tvg_id) == 1
    assert result.duplicate_tvg_id[0].tvg_id == "espn.us"
    assert len(result.duplicate_tvg_id[0].channels) == 2


def test_unused_epg_entries_detected():
    playlist = Playlist(name="p", channels=[_channel("ESPN", "http://x.com/a", "espn.us")])
    epg = [
        EPGChannel(id="espn.us", display_names=("ESPN",)),
        EPGChannel(id="cnn.us", display_names=("CNN",)),
    ]
    result = CompareWithXMLTVUseCase().execute(playlist, epg)
    assert len(result.unused_epg_entries) == 1
    assert result.unused_epg_entries[0].id == "cnn.us"


def test_empty_playlist_flags_every_epg_entry_as_unused():
    epg = [EPGChannel(id="espn.us"), EPGChannel(id="cnn.us")]
    result = CompareWithXMLTVUseCase().execute(Playlist(name="empty"), epg)
    assert len(result.unused_epg_entries) == 2
