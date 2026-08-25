"""Use case: when a channel-order slot has more variants than the
user wants to keep (e.g. "RCTI", "RCTI HD", "RCTI HD (720p)", "RCTI 2",
"RCTI Vision+", "RCTI V+", "RCTI R+" all pointing at the same
underlying broadcast), drop all but the best `max_variants` of them -
preferring ones a stream validation pass confirmed are actually
playable right now.

Reuses apply_channel_order.group_channels_by_slot() for the grouping
itself, so "which channels count as the same family" is defined in
exactly one place and can never disagree between ordering and
limiting - including the country guard that keeps a same-named foreign
channel (e.g. India's "INews (720p)") from ever being treated as a
variant of Indonesia's "iNews".

Channels that don't belong to any channel_order.txt slot are never
touched - this use case only prunes *listed* variant families, never
prunes down the general channel list.
"""

from __future__ import annotations

from iptv_manager.application.use_cases.apply_channel_order import group_channels_by_slot
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.entities.stream_validation_result import (
    StreamStatus,
    StreamValidationResult,
)


def online_urls_from_results(results: list[StreamValidationResult]) -> set[str]:
    """Build the `online_urls` set LimitChannelVariantsUseCase expects
    from a StreamValidationSummary's .results list."""
    return {result.channel.url.raw for result in results if result.status is StreamStatus.ONLINE}


class LimitChannelVariantsUseCase:
    """Pure domain logic, no I/O - the caller passes in stream
    validation results (or none, to skip playability-based ranking)."""

    def execute(
        self,
        priority_slots: list[list[str]],
        playlist: Playlist,
        online_urls: set[str] | None = None,
        max_variants: int = 2,
    ) -> Playlist:
        """online_urls: the StreamUrl.raw of every channel a stream
        validation pass confirmed is StreamStatus.ONLINE (see
        online_urls_from_results()). Pass None (e.g. when validation
        was skipped) to keep the first max_variants of each family in
        their existing order instead - still capped, just without a
        playability preference."""
        if not priority_slots or max_variants <= 0:
            return playlist

        channels = list(playlist)
        groups = group_channels_by_slot(priority_slots, channels)

        dropped: set[int] = set()
        for group in groups:
            if len(group) <= max_variants:
                continue
            if online_urls is None:
                keep = group[:max_variants]
            else:
                online = [i for i in group if channels[i].url.raw in online_urls]
                not_online = [i for i in group if channels[i].url.raw not in online_urls]
                # Prefer confirmed-playable variants; only fall back to
                # not-yet-confirmed ones if there aren't enough online
                # ones to fill the cap (e.g. validation was skipped, or
                # every variant happens to be down right now).
                keep = (online + not_online)[:max_variants]
            dropped.update(i for i in group if i not in keep)

        kept = [channel for index, channel in enumerate(channels) if index not in dropped]

        return Playlist(
            name=playlist.name,
            channels=kept,
            category=playlist.category,
            warnings=list(playlist.warnings),
        )
