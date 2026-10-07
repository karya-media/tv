"""Overrides spreadsheet writer (.xlsx) using openpyxl.

Exports every channel's current metadata plus two "correction" columns
(New tvg-id / New group-title) a human fills in by hand. The same
file, once edited, is read back by overrides_excel_reader and applied
via ApplyOverridesUseCase - a manual-correction workflow for metadata
mistakes that are easier to spot and fix by eye in a spreadsheet than
by editing category .m3u files or Python code directly (see the
TV9-tagged-as-India case fixed earlier in this project's history).

URL is the join key back to a channel (same key
MergePlaylistsUseCase already uses for duplicate detection) - included
as its own column so this file is self-contained and inspectable, but
it isn't meant to be edited.

write() re-syncs the file on every call when given `existing_overrides`
(see interfaces.cli.main, which does this on every `merge`/`report`
run): a channel no longer present in `playlist` simply isn't written -
its row disappears - and a brand-new channel gets a fresh row with
blank correction columns, while any correction already filled in for a
channel that still exists is carried forward untouched. A standing
correction is never silently lost just because the channel list
changed; it's also never left to haunt a channel it no longer applies
to once that channel is gone from every category file.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from iptv_manager.domain.entities.channel_override import ChannelOverride
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.infrastructure.reports.excel_sanitize import sanitize_for_excel

_HEADER_FONT = Font(bold=True)
_HEADERS = [
    "Source File",
    "Channel Name",
    "URL",
    "tvg-id",
    "New tvg-id",
    "group-title",
    "New group-title",
]


class OverridesExcelWriter:
    def write(
        self,
        playlist: Playlist,
        path: Path,
        existing_overrides: dict[str, ChannelOverride] | None = None,
    ) -> None:
        """existing_overrides: a {url: ChannelOverride} map (see
        overrides_excel_reader.read_overrides_excel, keyed by
        .url) - when given, a channel whose URL has a matching entry
        gets that entry's New tvg-id/New group-title carried into its
        row instead of starting blank, so re-running this on every
        pipeline run never discards a correction already on file."""
        existing_overrides = existing_overrides or {}

        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.title = "Overrides"

        sheet.append(_HEADERS)
        for cell in sheet[1]:
            cell.font = _HEADER_FONT

        for channel in playlist:
            carried = existing_overrides.get(channel.url.raw)
            sheet.append(
                [
                    sanitize_for_excel(channel.source_category or ""),
                    sanitize_for_excel(channel.name),
                    sanitize_for_excel(channel.url.raw),
                    sanitize_for_excel(str(channel.tvg_id)),
                    sanitize_for_excel(carried.new_tvg_id or "") if carried else "",
                    sanitize_for_excel(str(channel.group_title)),
                    sanitize_for_excel(carried.new_group_title or "") if carried else "",
                ]
            )

        self._autosize_columns(sheet)
        workbook.save(path)

    def _autosize_columns(self, sheet: Worksheet) -> None:
        for index, column_cells in enumerate(sheet.columns, start=1):
            length = max((len(str(cell.value)) for cell in column_cells if cell.value), default=0)
            column_letter = get_column_letter(index)
            sheet.column_dimensions[column_letter].width = min(max(length + 2, 10), 60)
