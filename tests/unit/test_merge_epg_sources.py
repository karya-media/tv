"""Unit tests for application.use_cases.merge_epg_sources."""

from iptv_manager.application.use_cases.merge_epg_sources import MergeEPGSourcesUseCase
from iptv_manager.domain.entities.epg_channel import EPGChannel
from iptv_manager.domain.entities.epg_programme import EPGProgramme


def _channel(channel_id: str, name: str = "X") -> EPGChannel:
    return EPGChannel(id=channel_id, display_names=(name,))


def _programme(channel_id: str, start: str, title: str = "Show") -> EPGProgramme:
    return EPGProgramme(channel_id=channel_id, start=start, stop=None, title=title)


def test_merges_channels_from_multiple_sources():
    result = MergeEPGSourcesUseCase().execute(
        [
            ([_channel("a.id")], []),
            ([_channel("b.id")], []),
        ]
    )
    assert {c.id for c in result.channels} == {"a.id", "b.id"}


def test_first_source_wins_for_a_duplicate_channel_id():
    result = MergeEPGSourcesUseCase().execute(
        [
            ([_channel("a.id", name="First Source Name")], []),
            ([_channel("a.id", name="Second Source Name")], []),
        ]
    )
    assert len(result.channels) == 1
    assert result.channels[0].display_names == ("First Source Name",)


def test_channel_id_matching_is_case_insensitive():
    result = MergeEPGSourcesUseCase().execute(
        [
            ([_channel("RCTI.id")], []),
            ([_channel("rcti.id")], []),
        ]
    )
    assert len(result.channels) == 1


def test_merges_programmes_from_multiple_sources():
    result = MergeEPGSourcesUseCase().execute(
        [
            ([], [_programme("a.id", "20260827100000 +0000")]),
            ([], [_programme("a.id", "20260827110000 +0000")]),
        ]
    )
    assert len(result.programmes) == 2


def test_duplicate_programme_by_channel_and_start_is_kept_once():
    result = MergeEPGSourcesUseCase().execute(
        [
            ([], [_programme("a.id", "20260827100000 +0000", title="From source 1")]),
            ([], [_programme("a.id", "20260827100000 +0000", title="From source 2")]),
        ]
    )
    assert len(result.programmes) == 1
    assert result.programmes[0].title == "From source 1"


def test_same_start_time_on_different_channels_is_not_a_duplicate():
    result = MergeEPGSourcesUseCase().execute(
        [
            ([], [_programme("a.id", "20260827100000 +0000")]),
            ([], [_programme("b.id", "20260827100000 +0000")]),
        ]
    )
    assert len(result.programmes) == 2


def test_empty_sources_list_returns_empty_result():
    result = MergeEPGSourcesUseCase().execute([])
    assert result.channels == []
    assert result.programmes == []
