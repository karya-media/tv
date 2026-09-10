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
        """Returns (raw_text, playlist).

        raw_text is the byte-for-byte content fetched from the source,
        completely unmodified - the caller should save *this* to
        data/categories/<category>.m3u if it wants that file to stay
        faithful to its upstream origin (group-title text, header
        attributes like url-tvg, attribute ordering/formatting, and
        anything else this project doesn't model, all preserved
        as-is). playlist is the parsed result, useful for reporting
        (channel counts, warnings) - never re-serialize it back to
        disk as a substitute for raw_text, since parsing normalizes
        semantic fields like group-title (see GroupTitle.parse()) and
        serialize() only reconstructs an approximation of the original
        formatting, not an exact copy. The categorization/ordering/
        variant-limiting "rules" apply at merge time, when category
        files are read back in - never at import/sync time.
        """
        raw_text = await source.fetch()
        playlist = self.parser.parse(raw_text, name=category, category=category)
        return raw_text, playlist
