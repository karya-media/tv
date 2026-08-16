"""Shared helpers for report-writer tests: builds a fully populated
ValidationReport from hand-written domain entities, with no I/O
(no HTTP, no ffprobe, no filesystem parsing) so writer tests are fast
and hermetic.
"""

from __future__ import annotations

from datetime import UTC, datetime

from iptv_manager.application.dto.validation_report import ValidationReport
from iptv_manager.application.use_cases.compare_with_xmltv import (
    DuplicateTvgIdInPlaylist,
    XMLTVComparisonResult,
)
from iptv_manager.application.use_cases.merge_playlists import (
    DuplicateTvgIdGroup,
    DuplicateUrlGroup,
    MergeResult,
)
from iptv_manager.application.use_cases.validate_logos import LogoValidationSummary
from iptv_manager.application.use_cases.validate_streams import StreamValidationSummary
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


def make_channel(
    name: str, url: str, tvg_id: str | None = None, logo_url: str | None = None
) -> Channel:
    return Channel(
        name=name,
        url=StreamUrl.parse(url),
        tvg_id=TvgId.parse(tvg_id),
        logo_url=logo_url,
        group_title=GroupTitle.parse("Sports"),
    )


def build_full_report() -> ValidationReport:
    espn = make_channel("ESPN", "http://x.com/espn.m3u8", "espn.us", "http://x.com/espn.png")
    fox = make_channel("Fox Sports", "http://x.com/fox.m3u8", "fox.us")
    dup_removed = make_channel("ESPN Dup", "http://x.com/espn.m3u8", "espn.us")

    master = Playlist(name="master", channels=[espn, fox])
    master.warnings.append("[sports] line 3: malformed #EXTINF, entry skipped: 'bad line'")

    merge_result = MergeResult(
        master=master,
        total_channels_before=3,
        total_channels_after=2,
        duplicate_urls=[
            DuplicateUrlGroup(key="http://x.com/espn.m3u8", kept=espn, removed=[dup_removed])
        ],
        duplicate_tvg_ids=[DuplicateTvgIdGroup(tvg_id="espn.us", channels=[espn, dup_removed])],
    )

    stream_summary = StreamValidationSummary(
        results=[
            StreamValidationResult(
                channel=espn, status=StreamStatus.ONLINE, http_status=200, response_time_ms=42.3
            ),
            StreamValidationResult(
                channel=fox, status=StreamStatus.OFFLINE, error_message="connection refused"
            ),
        ]
    )

    logo_summary = LogoValidationSummary(
        results=[
            LogoValidationResult(channel=espn, reachable=True, http_status=200),
            LogoValidationResult.missing(fox),
        ]
    )

    epg_comparison = XMLTVComparisonResult(
        missing_tvg_id=[],
        invalid_tvg_id=[fox],
        duplicate_tvg_id=[DuplicateTvgIdInPlaylist(tvg_id="espn.us", channels=[espn, dup_removed])],
        unused_epg_entries=[EPGChannel(id="unused.us", display_names=("Unused",))],
    )

    return ValidationReport(
        generated_at=datetime(2026, 7, 28, 10, 0, tzinfo=UTC),
        master_playlist_name="master",
        merge_result=merge_result,
        stream_summary=stream_summary,
        logo_summary=logo_summary,
        epg_comparison=epg_comparison,
    )


def build_minimal_report() -> ValidationReport:
    """A report with only the merge result available - simulating
    `iptv-manager report --skip-streams --skip-logos` with no --epg."""
    channel = make_channel("CNN", "http://x.com/cnn.m3u8", "cnn.us")
    master = Playlist(name="master", channels=[channel])
    merge_result = MergeResult(master=master, total_channels_before=1, total_channels_after=1)
    return ValidationReport(
        generated_at=datetime(2026, 7, 28, 10, 0, tzinfo=UTC),
        master_playlist_name="master",
        merge_result=merge_result,
    )
