"""Unit tests for application.use_cases.run_full_pipeline."""

import pytest

from iptv_manager.application.use_cases.run_full_pipeline import RunFullPipelineUseCase
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.epg_channel import EPGChannel
from iptv_manager.domain.entities.logo_validation_result import LogoValidationResult
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.entities.stream_validation_result import (
    StreamStatus,
    StreamValidationResult,
)
from iptv_manager.domain.value_objects.group_title import GroupTitle
from iptv_manager.domain.value_objects.stream_url import StreamUrl
from iptv_manager.domain.value_objects.tvg_id import TvgId


def _channel(name: str, url: str, tvg_id: str | None = None) -> Channel:
    return Channel(
        name=name,
        url=StreamUrl.parse(url),
        tvg_id=TvgId.parse(tvg_id),
        group_title=GroupTitle.parse("Sports"),
    )


class _AllOnlineValidator:
    async def validate(self, channel: Channel) -> StreamValidationResult:
        return StreamValidationResult(channel=channel, status=StreamStatus.ONLINE, http_status=200)


class _AllReachableLogoValidator:
    async def validate(self, channel: Channel) -> LogoValidationResult:
        return LogoValidationResult(channel=channel, reachable=True, http_status=200)


@pytest.mark.asyncio
async def test_merge_only_when_no_validators_given():
    playlist = Playlist(name="sports", channels=[_channel("ESPN", "http://x.com/a")])
    report = await RunFullPipelineUseCase().execute([playlist])

    assert report.merge_result is not None
    assert report.stream_summary is None
    assert report.logo_summary is None
    assert report.epg_comparison is None


@pytest.mark.asyncio
async def test_stream_validation_runs_when_validator_given():
    playlist = Playlist(name="sports", channels=[_channel("ESPN", "http://x.com/a")])
    report = await RunFullPipelineUseCase(stream_validator=_AllOnlineValidator()).execute(
        [playlist]
    )

    assert report.stream_summary is not None
    assert report.stream_summary.online_count == 1


@pytest.mark.asyncio
async def test_logo_validation_runs_when_validator_given():
    playlist = Playlist(name="sports", channels=[_channel("ESPN", "http://x.com/a")])
    report = await RunFullPipelineUseCase(logo_validator=_AllReachableLogoValidator()).execute(
        [playlist]
    )

    assert report.logo_summary is not None
    assert report.logo_summary.reachable_count == 1


@pytest.mark.asyncio
async def test_epg_comparison_runs_when_epg_channels_given():
    playlist = Playlist(name="sports", channels=[_channel("ESPN", "http://x.com/a", "espn.us")])
    epg = [EPGChannel(id="espn.us", display_names=("ESPN",))]

    report = await RunFullPipelineUseCase().execute([playlist], epg_channels=epg)

    assert report.epg_comparison is not None
    assert report.epg_comparison.invalid_tvg_id == []


@pytest.mark.asyncio
async def test_duplicate_url_across_playlists_is_removed_before_validation():
    espn_a = _channel("ESPN A", "http://x.com/dup")
    espn_b = _channel("ESPN B", "http://x.com/dup")
    playlist_1 = Playlist(name="sports", channels=[espn_a])
    playlist_2 = Playlist(name="news", channels=[espn_b])

    report = await RunFullPipelineUseCase(stream_validator=_AllOnlineValidator()).execute(
        [playlist_1, playlist_2]
    )

    assert report.merge_result.total_channels_after == 1
    assert report.stream_summary.total == 1
