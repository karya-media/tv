"""Playlist entity.

An ordered collection of channels, optionally scoped to one category
(the per-category .m3u files under data/categories/) or representing
the merged master playlist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from iptv_manager.domain.entities.channel import Channel


@dataclass(slots=True)
class Playlist:
    """Mutable on purpose (unlike Channel): a playlist is a container
    that use cases build up incrementally - parse, append channels,
    merge, dedupe - so cloning on every append would be wasteful.
    """

    name: str
    channels: list[Channel] = field(default_factory=list)
    category: str | None = None
    warnings: list[str] = field(default_factory=list)

    def add_channel(self, channel: Channel) -> None:
        self.channels.append(channel)

    def extend(self, channels: list[Channel]) -> None:
        self.channels.extend(channels)

    def __len__(self) -> int:
        return len(self.channels)

    def __iter__(self) -> Iterator[Channel]:
        return iter(self.channels)
