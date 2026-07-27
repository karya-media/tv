"""Port: where raw playlist text comes from.

Infrastructure implements this for local files and remote URLs, so
application use cases don't know or care which one they're talking to.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PlaylistSource(Protocol):
    """Something that can produce raw M3U text."""

    async def fetch(self) -> str:
        """Return the raw playlist content as text (already decoded)."""
        ...

    @property
    def identifier(self) -> str:
        """Human-readable origin, used in error messages and reports
        (a file path or a URL)."""
        ...
