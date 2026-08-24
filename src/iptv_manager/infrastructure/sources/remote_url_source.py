"""Remote URL playlist source.

Fetches a playlist over HTTP(S) using httpx, with a timeout and a
custom User-Agent (some IPTV providers reject requests with a blank or
missing User-Agent header).
"""

from __future__ import annotations

import gzip

import httpx

_FALLBACK_ENCODINGS = ("utf-8-sig", "utf-16", "cp1252")

# The first two bytes of a gzip stream (RFC 1952 magic number). Used to
# detect a *file-level* gzip (e.g. a URL ending in ".xml.gz" or
# ".m3u.gz" served as-is) which httpx does NOT auto-decompress - that
# only happens for transport-level "Content-Encoding: gzip", a
# different thing from the response body itself being a stored .gz
# file.
_GZIP_MAGIC = b"\x1f\x8b"


class PlaylistFetchError(RuntimeError):
    """Raised when the remote playlist could not be retrieved."""


class RemoteUrlPlaylistSource:
    """Implements domain.ports.PlaylistSource for a remote M3U URL."""

    def __init__(
        self,
        url: str,
        *,
        timeout: float = 15.0,
        user_agent: str = "IPTV-Playlist-Manager/0.1",
    ) -> None:
        self._url = url
        self._timeout = timeout
        self._user_agent = user_agent

    @property
    def identifier(self) -> str:
        return self._url

    async def fetch(self) -> str:
        headers = {"User-Agent": self._user_agent}
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                response = await client.get(self._url, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise PlaylistFetchError(f"timed out fetching {self._url}") from exc
        except httpx.HTTPStatusError as exc:
            raise PlaylistFetchError(
                f"HTTP {exc.response.status_code} fetching {self._url}"
            ) from exc
        except httpx.HTTPError as exc:
            raise PlaylistFetchError(f"failed to fetch {self._url}: {exc}") from exc

        return self._decode(response.content)

    async def fetch_bytes(self) -> bytes:
        """Like fetch(), but returns raw (gzip-decompressed if needed)
        bytes without ever text-decoding them.

        Meant for large XML sources (e.g. an aggregated multi-source
        XMLTV EPG file, which can decompress to several hundred MB or
        more): lxml can parse bytes directly and detect the document's
        real encoding itself, so skipping the str round-trip avoids
        holding two more full-size copies of the content in memory at
        once - the difference between this succeeding and the process
        being OOM-killed on a memory-constrained CI runner.
        """
        headers = {"User-Agent": self._user_agent}
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                response = await client.get(self._url, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise PlaylistFetchError(f"timed out fetching {self._url}") from exc
        except httpx.HTTPStatusError as exc:
            raise PlaylistFetchError(
                f"HTTP {exc.response.status_code} fetching {self._url}"
            ) from exc
        except httpx.HTTPError as exc:
            raise PlaylistFetchError(f"failed to fetch {self._url}: {exc}") from exc

        return self._maybe_decompress(response.content)

    def _maybe_decompress(self, raw_bytes: bytes) -> bytes:
        if not raw_bytes.startswith(_GZIP_MAGIC):
            return raw_bytes
        try:
            return gzip.decompress(raw_bytes)
        except OSError as exc:
            raise PlaylistFetchError(
                f"looked gzip-compressed but failed to decompress: {self._url}"
            ) from exc

    def _decode(self, raw_bytes: bytes) -> str:
        raw_bytes = self._maybe_decompress(raw_bytes)
        for encoding in _FALLBACK_ENCODINGS:
            try:
                return raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw_bytes.decode("latin-1")
