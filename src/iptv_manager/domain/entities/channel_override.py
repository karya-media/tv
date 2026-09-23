"""ChannelOverride entity.

Represents one row of a manually-maintained overrides spreadsheet
(see infrastructure.reports.overrides_excel_writer /
infrastructure.parsers.overrides_excel_reader): a correction to one
channel's tvg-id and/or group-title, keyed by its stream URL (the same
key MergePlaylistsUseCase already uses for duplicate detection, so
matching a spreadsheet row back to a channel is unambiguous).

Exists to let a human fix a specific channel's metadata by hand (e.g.
the TV9-tagged-as-India case fixed manually earlier in this project's
history) via a spreadsheet, instead of editing category .m3u files or
Python code directly.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChannelOverride:
    url: str
    new_tvg_id: str | None = None
    new_group_title: str | None = None

    @property
    def is_empty(self) -> bool:
        """True if neither correction column was actually filled in -
        a spreadsheet row that exists but has nothing to apply."""
        return not self.new_tvg_id and not self.new_group_title
