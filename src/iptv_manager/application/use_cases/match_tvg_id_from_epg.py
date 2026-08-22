"""Use case: fill in a channel's missing tvg-id by matching its name
*exactly* (after light normalization) against an external XMLTV EPG's
channel display names.

Deliberately as strict as backfill_tvg_id.py's within-playlist
matching, and for the same reason: a fuzzy/similarity-based match
risks assigning "RCTI 2" the EPG identity (and therefore programme
schedule) of "RCTI" itself, because the names merely look alike. That
would be worse than leaving tvg-id blank - it would show the wrong
schedule under a channel's name with false confidence. So a match
only counts here if the channel's name is character-for-character
identical (ignoring case and surrounding whitespace) to one of an EPG
channel's display names.

If a normalized name matches display names belonging to more than one
distinct EPG channel id, the match is ambiguous and is skipped - same
policy as backfill_tvg_id.py's handling of conflicting matches.
"""

from __future__ import annotations

from collections import defaultdict

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.epg_channel import EPGChannel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.tvg_id import TvgId


def _normalize(name: str) -> str:
    return name.strip().casefold()


class MatchTvgIdFromEpgUseCase:
    """Pure domain logic, no I/O - the caller fetches and parses the
    XMLTV source (see infrastructure.parsers.xmltv_parser) and passes
    in the resulting EPGChannel list."""

    def execute(self, playlist: Playlist, epg_channels: list[EPGChannel]) -> Playlist:
        epg_ids_by_name: dict[str, set[str]] = defaultdict(set)
        for epg_channel in epg_channels:
            for display_name in epg_channel.display_names:
                epg_ids_by_name[_normalize(display_name)].add(epg_channel.id)

        def match(channel: Channel) -> Channel:
            if channel.has_tvg_id:
                return channel
            candidates = epg_ids_by_name.get(_normalize(channel.name))
            if candidates is None or len(candidates) != 1:
                # No match, or the channel's name is ambiguous across
                # more than one distinct EPG channel - too uncertain
                # to guess.
                return channel
            (epg_id,) = candidates
            return channel.with_tvg_id(TvgId.parse(epg_id))

        return Playlist(
            name=playlist.name,
            channels=[match(channel) for channel in playlist],
            category=playlist.category,
            warnings=list(playlist.warnings),
        )
