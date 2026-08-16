"""JSON report writer.

Serializes a ValidationReport into a single JSON document. Domain
entities (Channel, StreamValidationResult, ...) are converted to plain
dicts by hand rather than via a generic dataclass-to-dict helper, so
each writer controls exactly what's exposed and so value objects like
TvgId/StreamUrl are serialized as their string form rather than their
internal shape.
"""

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
    return {
        "channel": _channel_to_dict(result.channel),
        "status": result.status.value,
        "http_status": result.http_status,
        "response_time_ms": result.response_time_ms,
        "redirected": result.redirected,
        "final_url": result.final_url,
        "error_message": result.error_message,
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
                    {"tvg_id": g.tvg_id, "channels": [c.name for c in g.channels]}
                    for g in mr.duplicate_tvg_ids
                ],
                "warnings": mr.master.warnings,
            }

        if report.stream_summary is not None:
            data["streams"] = {
                "total": report.stream_summary.total,
                "online": report.stream_summary.online_count,
                "offline": report.stream_summary.offline_count,
                "results": [_stream_result_to_dict(r) for r in report.stream_summary.results],
            }

        if report.logo_summary is not None:
            data["logos"] = {
                "total": report.logo_summary.total,
                "reachable": report.logo_summary.reachable_count,
                "missing": report.logo_summary.missing_count,
                "unreachable": report.logo_summary.unreachable_count,
                "results": [_logo_result_to_dict(r) for r in report.logo_summary.results],
            }

        if report.epg_comparison is not None:
            epg = report.epg_comparison
            data["epg"] = {
                "missing_tvg_id": [c.name for c in epg.missing_tvg_id],
                "invalid_tvg_id": [
                    {"name": c.name, "tvg_id": str(c.tvg_id)} for c in epg.invalid_tvg_id
                ],
                "duplicate_tvg_id": [
                    {"tvg_id": g.tvg_id, "channels": [c.name for c in g.channels]}
                    for g in epg.duplicate_tvg_id
                ],
                "unused_epg_entries": [e.id for e in epg.unused_epg_entries],
            }

        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
