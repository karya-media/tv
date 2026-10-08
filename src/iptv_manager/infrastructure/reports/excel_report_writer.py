"""Excel report writer (.xlsx) using openpyxl.

Produces a multi-sheet workbook - Summary, Streams, Logos, Duplicates,
EPG Issues - one sheet per concern, so a playlist maintainer can jump
straight to what they care about instead of scrolling one giant flat
table. Sheets are only added for data that's actually available in the
report (e.g. no "Streams" sheet if stream validation wasn't run).
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from iptv_manager.application.dto.validation_report import ValidationReport
from iptv_manager.infrastructure.reports.excel_sanitize import sanitize_for_excel

_HEADER_FONT = Font(bold=True)
_TITLE_FONT = Font(bold=True, size=14)


def _append(ws: Worksheet, values: list) -> None:  # type: ignore[type-arg]
    """ws.append(), sanitizing every value first - real-world IPTV
    source data occasionally carries an XML-illegal control character
    in a channel name or other free-text field, which would otherwise
    make openpyxl raise and the whole report fail to write."""
    ws.append([sanitize_for_excel(v) for v in values])


class ExcelReportWriter:
    def write(self, report: ValidationReport, path: Path) -> None:
        workbook = Workbook()
        summary_sheet = workbook.active
        assert summary_sheet is not None
        summary_sheet.title = "Summary"
        self._write_summary_sheet(summary_sheet, report)

        if report.stream_summary is not None:
            self._write_streams_sheet(workbook.create_sheet("Streams"), report)
        if report.logo_summary is not None:
            self._write_logos_sheet(workbook.create_sheet("Logos"), report)
        if report.merge_result is not None and report.merge_result.duplicate_urls:
            self._write_duplicates_sheet(workbook.create_sheet("Duplicates"), report)
        if report.epg_comparison is not None:
            self._write_epg_sheet(workbook.create_sheet("EPG Issues"), report)

        workbook.save(path)

    def _write_summary_sheet(self, ws: Worksheet, report: ValidationReport) -> None:
        _append(ws, ["IPTV Playlist Validation Report"])
        ws["A1"].font = _TITLE_FONT
        _append(ws, ["Generated at", report.generated_at.isoformat()])
        _append(ws, ["Master playlist", report.master_playlist_name])
        _append(ws, [])

        if report.merge_result is not None:
            mr = report.merge_result
            self._section_header(ws, "Merge summary")
            _append(ws, ["Channels before dedup", mr.total_channels_before])
            _append(ws, ["Channels after dedup", mr.total_channels_after])
            _append(ws, ["Duplicate URLs removed", mr.removed_duplicate_url_count])
            _append(ws, ["Duplicate tvg-id groups", len(mr.duplicate_tvg_ids)])
            _append(ws, [])

        if report.stream_summary is not None:
            summary = report.stream_summary
            self._section_header(ws, "Stream validation summary")
            _append(ws, ["Total streams", summary.total])
            _append(ws, ["Online", summary.online_count])
            _append(ws, ["Offline", summary.offline_count])
            _append(ws, [])

        if report.logo_summary is not None:
            logos = report.logo_summary
            self._section_header(ws, "Logo validation summary")
            _append(ws, ["Total channels", logos.total])
            _append(ws, ["Reachable", logos.reachable_count])
            _append(ws, ["Missing", logos.missing_count])
            _append(ws, ["Unreachable", logos.unreachable_count])
            _append(ws, [])

        if report.epg_comparison is not None:
            epg = report.epg_comparison
            self._section_header(ws, "EPG comparison summary")
            _append(ws, ["Missing tvg-id", len(epg.missing_tvg_id)])
            _append(ws, ["Invalid tvg-id", len(epg.invalid_tvg_id)])
            _append(ws, ["Duplicate tvg-id", len(epg.duplicate_tvg_id)])
            _append(ws, ["Unused EPG entries", len(epg.unused_epg_entries)])

    def _section_header(self, ws: Worksheet, title: str) -> None:
        _append(ws, [title])
        ws.cell(row=ws.max_row, column=1).font = _HEADER_FONT

    def _header_row(self, ws: Worksheet, headers: list[str]) -> None:
        _append(ws, headers)
        for cell in ws[ws.max_row]:
            cell.font = _HEADER_FONT

    def _write_streams_sheet(self, ws: Worksheet, report: ValidationReport) -> None:
        assert report.stream_summary is not None
        self._header_row(
            ws, ["Name", "Group", "URL", "Status", "HTTP Status", "Response Time (ms)", "Error"]
        )
        for result in report.stream_summary.results:
            _append(
                ws,
                [
                    result.channel.name,
                    str(result.channel.group_title),
                    str(result.channel.url),
                    result.status.value,
                    result.http_status,
                    result.response_time_ms,
                    result.error_message,
                ],
            )

    def _write_logos_sheet(self, ws: Worksheet, report: ValidationReport) -> None:
        assert report.logo_summary is not None
        self._header_row(ws, ["Name", "Logo URL", "Reachable", "HTTP Status", "Error"])
        for result in report.logo_summary.results:
            _append(
                ws,
                [
                    result.channel.name,
                    result.channel.logo_url,
                    result.reachable,
                    result.http_status,
                    result.error_message,
                ],
            )

    def _write_duplicates_sheet(self, ws: Worksheet, report: ValidationReport) -> None:
        assert report.merge_result is not None
        self._header_row(ws, ["Duplicate URL", "Kept Channel", "Removed Channel"])
        for group in report.merge_result.duplicate_urls:
            for removed in group.removed:
                _append(ws, [group.key, group.kept.name, removed.name])

    def _write_epg_sheet(self, ws: Worksheet, report: ValidationReport) -> None:
        epg = report.epg_comparison
        assert epg is not None
        self._header_row(ws, ["Issue Type", "Channel / EPG ID", "Detail"])
        for channel in epg.missing_tvg_id:
            _append(ws, ["Missing tvg-id", channel.name, ""])
        for channel in epg.invalid_tvg_id:
            _append(ws, ["Invalid tvg-id", channel.name, str(channel.tvg_id)])
        for group in epg.duplicate_tvg_id:
            _append(
                ws, ["Duplicate tvg-id", group.tvg_id, ", ".join(c.name for c in group.channels)]
            )
        for epg_channel in epg.unused_epg_entries:
            _append(
                ws, ["Unused EPG entry", epg_channel.id, epg_channel.primary_display_name or ""]
            )
