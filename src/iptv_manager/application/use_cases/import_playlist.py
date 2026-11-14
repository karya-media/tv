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

    async def execute(self, source: PlaylistSource, *, category: str) -> tuple[str, Playlist]:
        """Returns untouched source text and its parsed Playlist.

        JSON payloads are detected from their leading object/array
        delimiter and parsed through JSONPlaylistParser; other sources
        continue to use the injected parser (M3U by default).
        """
        raw_text = await source.fetch()
        if _looks_like_json(raw_text):
            from iptv_manager.infrastructure.parsers.json_parser import JSONPlaylistParser

            playlist = JSONPlaylistParser().parse(raw_text, name=category, category=category)
        else:
            playlist = self.parser.parse(raw_text, name=category, category=category)
        return raw_text, playlist


def _looks_like_json(raw_text: str) -> bool:
    stripped = raw_text.lstrip().lstrip("\ufeff")
    return bool(stripped) and stripped[0] in "[{"
