"""Port: turning raw M3U text into a Playlist, and back into text.

infrastructure.parsers.M3UParser is the concrete implementation. Use
cases depend on this Protocol so they stay parser-implementation
agnostic (e.g. testable with a fake parser, or swappable if a second
playlist format is added later).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from iptv_manager.domain.entities.playlist import Playlist


@runtime_checkable
class PlaylistParser(Protocol):
    def parse(self, raw_text: str, *, name: str, category: str | None = None) -> Playlist:
        """Parse raw M3U/M3U8 text into a Playlist. Must never raise on
        malformed individual entries - those are recorded as warnings
        on the returned Playlist instead."""
        ...

    def serialize(self, playlist: Playlist) -> str:
        """Render a Playlist back into valid M3U text."""
        ...
