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
"""

from __future__ import annotations

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.country import country_name_from_tvg_id
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

        prefixed_raw = f"{country};{channel.group_title.value}"
        return channel.with_group_title(GroupTitle.parse(prefixed_raw))
