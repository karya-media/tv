"""Unit tests for application.use_cases.categorize_by_country."""

from iptv_manager.application.use_cases.categorize_by_country import (
    CategorizeByCountryUseCase,
)
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.group_title import GroupTitle
from iptv_manager.domain.value_objects.stream_url import StreamUrl
from iptv_manager.domain.value_objects.tvg_id import TvgId


def _channel(name: str, tvg_id: str, group_title: str | None = None) -> Channel:
    return Channel(
        name=name,
        url=StreamUrl.parse(f"http://example.com/{name}.m3u8"),
        tvg_id=TvgId.parse(tvg_id),
        group_title=GroupTitle.parse(group_title),
    )


def _run(*channels: Channel) -> Playlist:
    playlist = Playlist(name="test", channels=list(channels))
    return CategorizeByCountryUseCase().execute(playlist)


def test_prefixes_group_title_with_country_from_tvg_id():
    result = _run(_channel("ANTV", "ANTV.id", "Nasional"))
    assert str(result.channels[0].group_title) == "Indonesia;Nasional"


def test_recognizes_quality_suffixed_tvg_id():
    result = _run(_channel("CCTV6", "CCTV6.cnHD", "News"))
    assert str(result.channels[0].group_title) == "China;News"


def test_does_not_double_prefix_already_tagged_channel():
    result = _run(_channel("RCTI", "RCTI.id", "Indonesia;Nasional"))
    assert str(result.channels[0].group_title) == "Indonesia;Nasional"


def test_channel_without_tvg_id_is_left_unchanged():
    result = _run(_channel("Mystery Channel", tvg_id="", group_title="Movies"))
    assert str(result.channels[0].group_title) == "Movies"


def test_unrecognized_tvg_id_suffix_is_left_unchanged():
    result = _run(_channel("Cartoon Network", "CartoonNetwork", "Kids"))
    assert str(result.channels[0].group_title) == "Kids"

    result = _run(_channel("Random", "556893", "Movies"))
    assert str(result.channels[0].group_title) == "Movies"


def test_uncategorized_channel_still_gets_country_prefix():
    result = _run(_channel("Some US Channel", "SomeChannel.usSD", None))
    assert str(result.channels[0].group_title) == "United States;Uncategorized"


def test_conflicting_pre_existing_country_is_trusted_over_tvg_id():
    # Real case: TV9 (an Indonesian local channel) was hand-tagged
    # group-title="Indonesia;..." but carried a mistaken tvg-id
    # suffix ".in" (India's ISO code, likely meant to be Indonesia's
    # ".id"). The already-curated "Indonesia" category must win rather
    # than being overwritten/prefixed with a derived "India".
    result = _run(_channel("TV9", "TV9.in", "Indonesia;Lainnya;RELIGION"))
    assert str(result.channels[0].group_title) == "Indonesia;Lainnya;RELIGION"


def test_matching_pre_existing_country_is_still_allowed_through():
    # Not blocked by the guard when the derived and existing country
    # actually agree - this is the normal, common case.
    result = _run(_channel("RCTI", "RCTI.id", "Indonesia;Nasional"))
    assert str(result.channels[0].group_title) == "Indonesia;Nasional"
