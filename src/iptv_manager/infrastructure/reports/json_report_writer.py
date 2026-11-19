from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from iptv_manager.application.dto.validation_report import ValidationReport
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.logo_validation_result import LogoValidationResult
from iptv_manager.domain.entities.stream_validation_result import StreamValidationResult


def _channel_to_dict(channel: Channel) -> dict[str, Any]:
    return {
        "name": channel.name,
        "url": str(channel.url),
        "tvg_id": str(channel.tvg_id) if channel.has_tvg_id else None,
        "group_title": str(channel.group_title),
        "logo_url": channel.logo_url,
        "source_category": channel.source_category,
    }


def _stream_result_to_dict(result: StreamValidationResult) -> dict[str, Any]:
    media = result.media_info
    return {
        "channel": _channel_to_dict(result.channel),
        "status": result.status.value,
        "http_status": result.http_status,
        "response_time_ms": result.response_time_ms,
        "redirected": result.redirected,
        "final_url": result.final_url,
        "content_type": result.content_type,
        "bytes_read": result.bytes_read,
        "error_message": result.error_message,
        "ffprobe": ({
            "resolution": media.resolution,
            "video_codec": media.video_codec,
            "audio_codec": media.audio_codec,
            "bitrate_kbps": media.bitrate_kbps,
            "fps": media.fps,
            "audio_channels": media.audio_channels,
            "audio_sample_rate": media.audio_sample_rate,
            "container_format": media.container_format,
            "duration_seconds": media.duration_seconds,
        } if media is not None else None),
    }


def _logo_result_to_dict(result: LogoValidationResult) -> dict[str, Any]:
    return {
        "channel": _channel_to_dict(result.channel),
        "reachable": result.reachable,
        "http_status": result.http_status,
        "error_message": result.error_message,
    }


class JSONReportWriter:
    def write(self, report: ValidationReport, path: Path) -> None:
        data: dict[str, Any] = {
            "generated_at": report.generated_at.isoformat(),
            "master_playlist_name": report.master_playlist_name,
        }
        if report.merge_result is not None:
            mr = report.merge_result
            data["merge"] = {
                "total_channels_before": mr.total_channels_before,
                "total_channels_after": mr.total_channels_after,
                "duplicate_urls_removed": mr.removed_duplicate_url_count,
                "duplicate_tvg_id_groups": [
                    {"tvg_id": group.tvg_id, "channels": [channel.name for channel in group.channels]}
                    for group in mr.duplicate_tvg_ids
                ],
                "warnings": mr.master.warnings,
            }
        if report.stream_summary is not None:
            summary = report.stream_summary
            data["streams"] = {
                "total": summary.total,
                "online": summary.online_count,
                "offline": summary.offline_count,
                "ffprobe_analyzed": summary.ffprobe_count,
                "excluded_from_playlist": [
                    result.channel.name for result in summary.results
                    if result.channel.url.raw in summary.excluded_urls
                ],
                "results": [_stream_result_to_dict(result) for result in summary.results],
            }
        if report.logo_summary is not None:
            data["logos"] = {
                "total": report.logo_summary.total,
                "reachable": report.logo_summary.reachable_count,
                "missing": report.logo_summary.missing_count,
                "unreachable": report.logo_summary.unreachable_count,
                "results": [_logo_result_to_dict(result) for result in report.logo_summary.results],
            }
        if report.epg_comparison is not None:
            epg = report.epg_comparison
            data["epg"] = {
                "missing_tvg_id": [channel.name for channel in epg.missing_tvg_id],
                "invalid_tvg_id": [
                    {"name": channel.name, "tvg_id": str(channel.tvg_id)}
                    for channel in epg.invalid_tvg_id
                ],
                "duplicate_tvg_id": [
                    {"tvg_id": group.tvg_id, "channels": [channel.name for channel in group.channels]}
                    for group in epg.duplicate_tvg_id
                ],
                "unused_epg_entries": [entry.id for entry in epg.unused_epg_entries],
            }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
