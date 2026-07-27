"""Use case: import a single category playlist from a local file or a
remote URL, and parse it into domain entities.
"""

from __future__ import annotations

from dataclasses import dataclass

from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.ports.playlist_parser import PlaylistParser
from iptv_manager.domain.ports.playlist_source import PlaylistSource


@dataclass(slots=True)
class ImportPlaylistUseCase:
    """Orchestrates: fetch raw text from a source, then parse it into a
    Playlist. Depends only on ports - concrete parsers/sources are
    wired in at the interfaces layer (CLI, API), never imported here.
    """

    parser: PlaylistParser

    async def execute(self, source: PlaylistSource, *, category: str) -> Playlist:
        raw_text = await source.fetch()
        return self.parser.parse(raw_text, name=category, category=category)
