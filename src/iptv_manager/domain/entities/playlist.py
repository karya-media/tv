"""Playlist entity.

An ordered collection of channels, optionally scoped to one category
(the per-category .m3u files under data/categories/) or representing
the merged master playlist.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

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
    # The `url-tvg` attribute on this file's own "#EXTM3U ..." header,
    # if it had one - a source file's stated EPG preference, captured
    # so callers (see merge-epg's auto-discovery) can use it without
    # having to re-read/re-parse the raw file themselves. Not carried
    # forward automatically through merges; a use case that cares
    # about it reads it explicitly per source playlist.
    epg_url: str | None = None

    def add_channel(self, channel: Channel) -> None:
        self.channels.append(channel)

    def extend(self, channels: list[Channel]) -> None:
        self.channels.extend(channels)

    def __len__(self) -> int:
        return len(self.channels)

    def __iter__(self) -> Iterator[Channel]:
        return iter(self.channels)
