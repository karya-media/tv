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

Matching happens in two passes:

1. Exact match against every explicitly-listed alternative in
   data/channel_order.txt (e.g. "RCTI|RCTI HD|RCTI 2|RCTI Vision+").
   This is unambiguous and never mis-groups a channel.

2. Prefix fallback: any channel *still unplaced* after pass 1 whose
   name starts with a slot's first ("primary") alternative, followed
   by a clear word boundary (space, "+", "-", "(", or "."), is pinned
   to that slot too - so a brand-new source spelling like "RCTI Prime"
   gets grouped automatically without needing to be listed by hand.

   Pass 2 only runs after *all* of pass 1 has completed for every
   slot, so a channel with its own explicit slot elsewhere in the
   file (e.g. "RCTI World", which is a genuinely different channel
   that happens to share the "RCTI" brand prefix) is already placed
   by then and is never stolen by another slot's prefix rule.
"""

from __future__ import annotations

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist

# Characters that may immediately follow a slot's primary name for a
# prefix match to count - i.e. a real word boundary, not the middle of
# a longer, unrelated channel name. Deliberately excludes bare digits:
# real-world brand collisions exist where a *different* broadcaster
# happens to share a name prefix followed directly by a number (e.g.
# Vietnam's "SCTV11".."SCTV19" vs. Indonesia's "SCTV" - confirmed via
# their differing tvg-id country suffixes, ".vn" vs ".id"). Requiring
# an explicit separator (space, "+", "-", "(", ".") before any digit
# avoids that class of false positive; "RCTI 2" still matches (space
# before the digit), "SCTV11" no longer does (digit right after the
# letters, no separator).
_PREFIX_BOUNDARY_CHARS = " +-()."


def _normalize(name: str) -> str:
    return name.strip().casefold()


def _is_prefix_match(channel_name: str, primary: str) -> bool:
    normalized = _normalize(channel_name)
    primary_norm = _normalize(primary)
    if not primary_norm or not normalized.startswith(primary_norm):
        return False
    remainder = normalized[len(primary_norm) :]
    return not remainder or remainder[0] in _PREFIX_BOUNDARY_CHARS


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

        def exact_matches(alternatives: list[str]) -> set[int]:
            matches: set[int] = set()
            for name in alternatives:
                matches.update(indices_by_name.get(_normalize(name), []))
            return matches

        # Every index that's an exact match for *some* slot, computed
        # up front across the whole file - not just the slots seen so
        # far. This is what lets a channel with its own explicit slot
        # later in the file (e.g. "RCTI World") stay reserved for that
        # slot even while an earlier slot ("RCTI") is being placed, so
        # its prefix rule never has a chance to steal it.
        exact_claimed: set[int] = set()
        for alternatives in priority_slots:
            exact_claimed |= exact_matches(alternatives)

        placed = [False] * len(channels)
        ordered: list[Channel] = []

        for alternatives in priority_slots:
            if not alternatives:
                continue
            primary = alternatives[0]
            slot_indices = exact_matches(alternatives) | {
                index
                for index, channel in enumerate(channels)
                if index not in exact_claimed
                and not placed[index]
                and _is_prefix_match(channel.name, primary)
            }
            for index in sorted(i for i in slot_indices if not placed[i]):
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

