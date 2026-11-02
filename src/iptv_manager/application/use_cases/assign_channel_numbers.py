"""Use case: assign sequential tvg-chno (channel number) values to a
Playlist's channels, in their *current* order.

Meant to run as the very last step before publishing a bundle, after
ApplyChannelOrderUseCase has finalized that bundle's channel order
(see interfaces.cli.main._publish_bundles) - so a channel pinned first
via data/channel_order.txt also becomes tvg-chno="1" in the published
file, giving players that support numeric remote-control navigation a
stable, predictable channel list that matches this project's own
ordering rules, not just whatever arbitrary order channels happened to
merge in.

Each bundle is numbered independently starting from 1 - "indonesia"
and "all" each get their own 1, 2, 3, ... sequence, since they're
meant to be usable as self-contained playlists in their own right.
"""

from __future__ import annotations

from iptv_manager.domain.entities.playlist import Playlist


class AssignChannelNumbersUseCase:
    """Pure domain logic, no I/O."""

    def execute(self, playlist: Playlist, start: int = 1) -> Playlist:
        return Playlist(
            name=playlist.name,
            channels=[
                channel.with_tvg_chno(number)
                for number, channel in enumerate(playlist, start=start)
            ],
            category=playlist.category,
            warnings=list(playlist.warnings),
            epg_url=playlist.epg_url,
        )
