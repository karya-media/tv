"""CSV report writer.

Produces one row per channel, combining whichever validation results
are available (stream status, logo status) into a single flat table -
CSV can't represent nested structure, so this intentionally stays flat
rather than trying to mirror the JSON report's full detail.

Logo results are joined to stream results by the channel's normalized
URL key rather than Python object identity, since the two summaries
may hold separately-constructed Channel instances that are logically
the same channel.
"""

from __future__ import annotations

import csv
from pathlib import Path

from iptv_manager.application.dto.validation_report import ValidationReport
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.logo_validation_result import LogoValidationResult

_FIELDNAMES = [
    "name",
    "group_title",
    "tvg_id",
    "url",
    "stream_status",
    "http_status",
    "response_time_ms",
    "logo_status",
]


def _logo_status(result: LogoValidationResult) -> str:
    if result.reachable:
        return "reachable"
    if result.error_message == "no logo_url set":
        return "missing"
    return "unreachable"


class CSVReportWriter:
    def write(self, report: ValidationReport, path: Path) -> None:
        logo_by_url: dict[str, str] = {}
        if report.logo_summary is not None:
            for result in report.logo_summary.results:
                logo_by_url[result.channel.url.normalized_key] = _logo_status(result)

        rows: list[dict[str, str | float | None]] = []

        if report.stream_summary is not None:
            for stream_result in report.stream_summary.results:
                rows.append(
                    self._row(
                        stream_result.channel,
                        logo_by_url,
                        status=stream_result.status.value,
                        http_status=stream_result.http_status,
                        response_time_ms=stream_result.response_time_ms,
                    )
                )
        elif report.merge_result is not None:
            for channel in report.merge_result.master:
                rows.append(self._row(channel, logo_by_url))

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

    def _row(
        self,
        channel: Channel,
        logo_by_url: dict[str, str],
        *,
        status: str = "",
        http_status: int | None = None,
        response_time_ms: float | None = None,
    ) -> dict[str, str | float | None]:
        return {
            "name": channel.name,
            "group_title": str(channel.group_title),
            "tvg_id": str(channel.tvg_id) if channel.has_tvg_id else "",
            "url": str(channel.url),
            "stream_status": status,
            "http_status": http_status if http_status is not None else "",
            "response_time_ms": response_time_ms if response_time_ms is not None else "",
            "logo_status": logo_by_url.get(channel.url.normalized_key, ""),
        }
