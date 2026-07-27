"""Use case: compare a playlist's tvg-id values against an XMLTV EPG.

Reports four distinct situations, each actionable in a different way:
- missing_tvg_id:    channel has no tvg-id at all -> can't match EPG.
- invalid_tvg_id:    channel has a tvg-id, but it isn't in the EPG.
- duplicate_tvg_id:  two+ channels in the playlist share one tvg-id.
- unused_epg_entries: EPG channels no playlist channel references -
                       harmless, but useful for pruning a bloated EPG file.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.epg_channel import EPGChannel
from iptv_manager.domain.entities.playlist import Playlist


@dataclass(slots=True)
class DuplicateTvgIdInPlaylist:
    tvg_id: str
    channels: list[Channel]


@dataclass(slots=True)
class XMLTVComparisonResult:
    missing_tvg_id: list[Channel] = field(default_factory=list)
    invalid_tvg_id: list[Channel] = field(default_factory=list)
    duplicate_tvg_id: list[DuplicateTvgIdInPlaylist] = field(default_factory=list)
    unused_epg_entries: list[EPGChannel] = field(default_factory=list)


class CompareWithXMLTVUseCase:
    """Pure domain logic, no I/O - the playlist and EPG channels are
    already parsed by the time this runs."""

    def execute(self, playlist: Playlist, epg_channels: list[EPGChannel]) -> XMLTVComparisonResult:
        epg_ids = {epg.id for epg in epg_channels}

        missing: list[Channel] = []
        invalid: list[Channel] = []
        tvg_id_groups: dict[str, list[Channel]] = {}
        referenced_epg_ids: set[str] = set()

        for channel in playlist:
            if not channel.has_tvg_id:
                missing.append(channel)
                continue

            tvg_id_value = str(channel.tvg_id)
            tvg_id_groups.setdefault(tvg_id_value, []).append(channel)

            if tvg_id_value in epg_ids:
                referenced_epg_ids.add(tvg_id_value)
            else:
                invalid.append(channel)

        duplicates = [
            DuplicateTvgIdInPlaylist(tvg_id=tvg_id, channels=channels)
            for tvg_id, channels in tvg_id_groups.items()
            if len(channels) > 1
        ]

        unused_epg = [epg for epg in epg_channels if epg.id not in referenced_epg_ids]

        return XMLTVComparisonResult(
            missing_tvg_id=missing,
            invalid_tvg_id=invalid,
            duplicate_tvg_id=duplicates,
            unused_epg_entries=unused_epg,
        )
