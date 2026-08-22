"""Use case: fill in a channel's missing tvg-id by finding another
channel *in the same merged playlist* whose display name is exactly
identical (after trimming whitespace and ignoring case) and that
already has a tvg-id.

This is the safe half of tvg-id backfilling - it never guesses. Two
entries named "RCTI" are extremely likely to be the exact same
channel pulled from two different upstream sources, one of which
happened to carry a tvg-id and one of which didn't; two entries named
"RCTI" and "RCTI 2" are NOT the same channel and are never touched,
because the match requires the full name to be identical, not merely
similar. See categorize_by_country.py for the analogous
tvg-id-derived country-tagging use case, and
apply_channel_order.py for where a looser *prefix* match is safe to
use instead (grouping visual order carries much lower risk than
mis-tagging EPG identity).

If a name has more than one distinct existing tvg-id among its
entries (a genuine data conflict upstream), nothing is touched -
picking one would be a guess, not a fact recovered from the data.
"""

from __future__ import annotations

from collections import defaultdict

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.tvg_id import TvgId


def _normalize(name: str) -> str:
    return name.strip().casefold()


class BackfillTvgIdFromExactNameUseCase:
    """Pure domain logic, no I/O."""

    def execute(self, playlist: Playlist) -> Playlist:
        channels = list(playlist)

        known_tvg_id_by_name: dict[str, set[str]] = defaultdict(set)
        for channel in channels:
            if channel.has_tvg_id:
                known_tvg_id_by_name[_normalize(channel.name)].add(channel.tvg_id.value)

        def backfill(channel: Channel) -> Channel:
            if channel.has_tvg_id:
                return channel
            candidates = known_tvg_id_by_name.get(_normalize(channel.name))
            if candidates is None or len(candidates) != 1:
                # No match, or the same name maps to conflicting
                # tvg-ids elsewhere - too ambiguous to guess.
                return channel
            (tvg_id_value,) = candidates
            return channel.with_tvg_id(TvgId.parse(tvg_id_value))

        return Playlist(
            name=playlist.name,
            channels=[backfill(channel) for channel in channels],
            category=playlist.category,
            warnings=list(playlist.warnings),
        )
