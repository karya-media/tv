"""Unit tests for the validate_streams and validate_logos use cases,
using hand-written fake validators (no HTTP, no mocking library) to
prove the use cases depend only on the port, not any concrete
implementation.
"""

import pytest

from iptv_manager.application.use_cases.validate_logos import ValidateLogosUseCase
from iptv_manager.application.use_cases.validate_streams import ValidateStreamsUseCase
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.logo_validation_result import LogoValidationResult
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.entities.stream_validation_result import (
    StreamStatus,
    StreamValidationResult,
)
from iptv_manager.domain.value_objects.group_title import GroupTitle
from iptv_manager.domain.value_objects.stream_url import StreamUrl


def _channel(name: str, url: str = "http://x.com/a") -> Channel:
    return Channel(name=name, url=StreamUrl.parse(url), group_title=GroupTitle.parse("Test"))


class FakeStreamValidator:
    """A fake that alternates ONLINE/OFFLINE by channel name, with no
    network calls at all."""

    async def validate(self, channel: Channel) -> StreamValidationResult:
        status = StreamStatus.ONLINE if "online" in channel.name else StreamStatus.OFFLINE
        return StreamValidationResult(channel=channel, status=status)


class FakeLogoValidator:
    async def validate(self, channel: Channel) -> LogoValidationResult:
        return LogoValidationResult(channel=channel, reachable="logo" in channel.name)


@pytest.mark.asyncio
async def test_validate_streams_use_case_summarizes_results():
    playlist = Playlist(
        name="p",
        channels=[_channel("online 1"), _channel("offline 1"), _channel("online 2")],
    )
    summary = await ValidateStreamsUseCase(validator=FakeStreamValidator()).execute(playlist)

    assert summary.total == 3
    assert summary.online_count == 2
    assert summary.offline_count == 1
    assert summary.count_by_status(StreamStatus.OFFLINE) == 1


@pytest.mark.asyncio
async def test_validate_streams_use_case_empty_playlist():
    summary = await ValidateStreamsUseCase(validator=FakeStreamValidator()).execute(
        Playlist(name="empty")
    )
    assert summary.total == 0


@pytest.mark.asyncio
async def test_validate_logos_use_case_summarizes_results():
    playlist = Playlist(name="p", channels=[_channel("with logo"), _channel("no image")])
    summary = await ValidateLogosUseCase(validator=FakeLogoValidator()).execute(playlist)

    assert summary.total == 2
    assert summary.reachable_count == 1
