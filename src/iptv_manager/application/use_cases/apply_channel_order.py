"""Use case: reorder a merged master Playlist so specific channels
appear at specific positions, regardless of which category file (and
therefore which alphabetical merge position) they originally came
from.

Kept as its own use case, applied *after* MergePlaylistsUseCase,
rather than folded into the merge itself: ordering is a presentation
concern the user controls via data/channel_order.txt, while merging
(dedup, tvg-id flagging) is a data-integrity concern. Separating them
means the merge's duplicate-detection semantics never have to think
about ordering, and the ordering logic never has to think about
duplicates.
"""

from __future__ import annotations

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist


def _normalize(name: str) -> str:
    return name.strip().casefold()


class ApplyChannelOrderUseCase:
    """Pure domain logic, no I/O - the caller reads
    data/channel_order.txt and passes in the parsed name list."""

    def execute(self, playlist: Playlist, priority_names: list[str]) -> Playlist:
        if not priority_names:
            return playlist

        channels = list(playlist)

        # Group channel *indices* (not values) by normalized name, so
        # placement is unambiguous even if two channels are otherwise
        # identical - no reliance on Channel equality/hashing.
        indices_by_name: dict[str, list[int]] = {}
        for index, channel in enumerate(channels):
            indices_by_name.setdefault(_normalize(channel.name), []).append(index)

        placed = [False] * len(channels)
        ordered: list[Channel] = []

        seen_priority_keys: set[str] = set()
        for name in priority_names:
            key = _normalize(name)
            if key in seen_priority_keys:
                continue  # duplicate line in channel_order.txt, ignore the repeat
            seen_priority_keys.add(key)
            for index in indices_by_name.get(key, []):
                ordered.append(channels[index])
                placed[index] = True

        # Everything not pinned keeps its original relative order,
        # appended after every pinned channel.
        ordered.extend(channel for index, channel in enumerate(channels) if not placed[index])

        return Playlist(
            name=playlist.name,
            channels=ordered,
            category=playlist.category,
            warnings=list(playlist.warnings),
        )
