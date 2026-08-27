"""Use case: prefix each channel's group-title with its source
country, derived from the ISO country-code suffix iptv-org embeds in
tvg-id (see domain.value_objects.country).

Kept as its own use case, applied *after* MergePlaylistsUseCase - like
ApplyChannelOrderUseCase, it's a presentation/organization concern
layered on top of the merged master playlist, not part of merging
itself.

Channels whose tvg-id carries no recognizable country-code suffix are
left with their existing group-title unchanged, so they still fall
into GroupTitle's "Uncategorized" bucket (or whatever category they
already had) rather than being mis-tagged with a guessed country.

Channels whose group-title is already prefixed with the same country
name (e.g. the ~200 Indonesian channels already tagged
"Indonesia;Nasional" by hand) are not double-prefixed:
GroupTitle.parse() dedupes repeated ";"-separated segments, so
"Indonesia;Indonesia;Nasional" collapses back down to
"Indonesia;Nasional".

Channels whose group-title already starts with a *different* known
country name are left alone entirely - the tvg-id is trusted less
than an explicit, already-curated category. This protects against a
confirmed real case: several entries in data/categories/02_lokal.m3u
and 03_TVRI Daerah.m3u (TVRI's own regional stations, TV9, Elshinta
TV, and others) were hand-tagged group-title="Indonesia;..." but
carried tvg-id values ending in ".in" - a plausible mix-up with
Indonesia's actual ISO code ".id" - which would otherwise resolve to
India and produce a nonsensical "India;Indonesia;..." group-title.
"""

from __future__ import annotations

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.country import COUNTRY_NAMES, country_name_from_tvg_id
from iptv_manager.domain.value_objects.group_title import GroupTitle


class CategorizeByCountryUseCase:
    """Pure domain logic, no I/O."""

    def execute(self, playlist: Playlist) -> Playlist:
        return Playlist(
            name=playlist.name,
            channels=[self._categorize(channel) for channel in playlist],
            category=playlist.category,
            warnings=list(playlist.warnings),
        )

    def _categorize(self, channel: Channel) -> Channel:
        if not channel.has_tvg_id:
            return channel

        country = country_name_from_tvg_id(channel.tvg_id.value)
        if country is None:
            return channel

        existing_country = _leading_country(channel.group_title.value)
        if existing_country is not None and existing_country != country:
            return channel

        prefixed_raw = f"{country};{channel.group_title.value}"
        return channel.with_group_title(GroupTitle.parse(prefixed_raw))


def _leading_country(group_title: str) -> str | None:
    """If group_title already starts with a recognized country name
    (as a full ";"-separated segment, not just any substring), return
    it; otherwise None."""
    first_segment = group_title.split(";", 1)[0].strip()
    return first_segment if first_segment in COUNTRY_NAMES.values() else None
