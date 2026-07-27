"""Local filesystem playlist source.

Reads a local .m3u/.m3u8 file, handling UTF-8 with or without a BOM
and falling back to common legacy encodings so a mis-tagged or
non-UTF-8 file doesn't crash the import.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

# Order matters: utf-8-sig also correctly decodes plain UTF-8 (with no
# BOM), so it's tried first. utf-16 catches Windows-authored playlists
# saved with a UTF-16 BOM. cp1252/latin-1 are common legacy fallbacks
# seen in older IPTV provider exports.
_FALLBACK_ENCODINGS = ("utf-8-sig", "utf-16", "cp1252")


class PlaylistFileNotFoundError(FileNotFoundError):
    """Raised when the given path doesn't exist or isn't a file."""


class LocalFilePlaylistSource:
    """Implements domain.ports.PlaylistSource for a file on disk."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    @property
    def identifier(self) -> str:
        return str(self._path)

    async def fetch(self) -> str:
        if not self._path.is_file():
            raise PlaylistFileNotFoundError(f"playlist file not found: {self._path}")
        # File I/O is fast and local, but running it in a thread keeps
        # this source's interface consistent (async) with the remote
        # one, without blocking the event loop on larger files.
        return await asyncio.to_thread(self._read_with_fallback)

    def _read_with_fallback(self) -> str:
        raw_bytes = self._path.read_bytes()
        for encoding in _FALLBACK_ENCODINGS:
            try:
                return raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        # Last resort: latin-1 never fails (it maps every byte to a
        # code point), so we never lose the file entirely.
        return raw_bytes.decode("latin-1")
