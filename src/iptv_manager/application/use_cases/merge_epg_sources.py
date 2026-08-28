"""Use case: merge several already-parsed XMLTV sources into one
combined (channels, programmes) result, filtered to only the channels
the caller actually wants (in practice: every tvg-id present in
master.m3u).

This is the EPG counterpart to MergePlaylistsUseCase (which combines
several category .m3u files into master.m3u) - conceptually the same
idea, "combine several sources of the same kind of data into one",
but for programme guide data instead of channel listings.

Deliberately takes already-parsed EPGChannel/EPGProgramme lists rather
than raw source bytes: fetching and parsing (with the channel-id
filter applied *during* the streaming parse - see XMLTVParser) is I/O
and stays in the infrastructure/CLI layer, consistent with every other
use case in this project. Merging itself is pure, small, and easy to
reason about and test once the (already filtered-down-to-relevant-size)
data is in hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from iptv_manager.domain.entities.epg_channel import EPGChannel
from iptv_manager.domain.entities.epg_programme import EPGProgramme


@dataclass
class EPGMergeResult:
    channels: list[EPGChannel] = field(default_factory=list)
    programmes: list[EPGProgramme] = field(default_factory=list)


class MergeEPGSourcesUseCase:
    """Pure domain logic, no I/O."""

    def execute(
        self, sources: list[tuple[list[EPGChannel], list[EPGProgramme]]]
    ) -> EPGMergeResult:
        """sources: one (channels, programmes) pair per input file, in
        priority order - the first source to define a given channel id
        or an exact (channel_id, start) programme wins; later sources
        contribute only what earlier ones didn't already provide."""
        channels_by_id: dict[str, EPGChannel] = {}
        seen_programme_keys: set[tuple[str, str]] = set()
        programmes: list[EPGProgramme] = []

        for source_channels, source_programmes in sources:
            for channel in source_channels:
                channel_key = channel.id.casefold()
                if channel_key not in channels_by_id:
                    channels_by_id[channel_key] = channel

            for programme in source_programmes:
                programme_key = (programme.channel_id.casefold(), programme.start)
                if programme_key in seen_programme_keys:
                    continue
                seen_programme_keys.add(programme_key)
                programmes.append(programme)

        return EPGMergeResult(channels=list(channels_by_id.values()), programmes=programmes)
