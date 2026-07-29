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

    def execute(self, priority_slots: list[list[str]], playlist: Playlist) -> Playlist:
        if not priority_slots:
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

        already_matched_indices: set[int] = set()
        for alternatives in priority_slots:
            # A slot's alternatives may match different channels (or
            # the same one twice under different spellings) - collect
            # every matching index first, then place them in their
            # original relative order, once each.
            slot_indices: set[int] = set()
            for name in alternatives:
                key = _normalize(name)
                for index in indices_by_name.get(key, []):
                    slot_indices.add(index)

            for index in sorted(slot_indices - already_matched_indices):
                ordered.append(channels[index])
                placed[index] = True
                already_matched_indices.add(index)

        # Everything not pinned keeps its original relative order,
        # appended after every pinned channel.
        ordered.extend(channel for index, channel in enumerate(channels) if not placed[index])

        return Playlist(
            name=playlist.name,
            channels=ordered,
            category=playlist.category,
            warnings=list(playlist.warnings),
        )
