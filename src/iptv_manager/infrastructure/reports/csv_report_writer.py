"""Flat CSV report combining channel metadata and validation results."""

from __future__ import annotations

import csv
from pathlib import Path

from iptv_manager.application.dto.validation_report import ValidationReport
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.logo_validation_result import LogoValidationResult

_FIELDNAMES = [
    "name", "group_title", "tvg_id", "url", "stream_status", "http_status",
    "content_type", "bytes_read", "response_time_ms", "ffprobe_resolution",
    "video_codec", "audio_codec", "container_format", "excluded_from_playlist", "logo_status",
]


def _logo_status(result: LogoValidationResult) -> str:
    if result.reachable:
        return "reachable"
    return "missing" if result.error_message == "no logo_url set" else "unreachable"


class CSVReportWriter:
    def write(self, report: ValidationReport, path: Path) -> None:
        logos: dict[str, str] = {}
        if report.logo_summary:
            logos = {result.channel.url.normalized_key: _logo_status(result)
                     for result in report.logo_summary.results}
        rows: list[dict[str, object]] = []
        if report.stream_summary:
            for result in report.stream_summary.results:
                media = result.media_info
                channel = result.channel
                rows.append({
                    "name": channel.name, "group_title": str(channel.group_title),
                    "tvg_id": str(channel.tvg_id) if channel.has_tvg_id else "",
                    "url": str(channel.url), "stream_status": result.status.value,
                    "http_status": result.http_status or "", "content_type": result.content_type or "",
                    "bytes_read": result.bytes_read, "response_time_ms": result.response_time_ms or "",
                    "ffprobe_resolution": media.resolution if media else "",
                    "video_codec": media.video_codec if media else "",
                    "audio_codec": media.audio_codec if media else "",
                    "container_format": media.container_format if media else "",
                    "excluded_from_playlist": channel.url.raw in report.stream_summary.excluded_urls,
                    "logo_status": logos.get(channel.url.normalized_key, ""),
                })
        elif report.merge_result:
            for channel in report.merge_result.master:
                rows.append({"name": channel.name, "group_title": str(channel.group_title),
                             "tvg_id": str(channel.tvg_id) if channel.has_tvg_id else "",
                             "url": str(channel.url), "stream_status": "", "http_status": "",
                             "content_type": "", "bytes_read": "", "response_time_ms": "",
                             "ffprobe_resolution": "", "video_codec": "", "audio_codec": "",
                             "container_format": "", "excluded_from_playlist": False,
                             "logo_status": logos.get(channel.url.normalized_key, "")})
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=_FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
