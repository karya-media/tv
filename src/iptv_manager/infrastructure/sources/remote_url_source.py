"""Remote URL playlist source.

Fetches a playlist over HTTP(S) using httpx, with a timeout and a
custom User-Agent (some IPTV providers reject requests with a blank or
missing User-Agent header).
"""

from __future__ import annotations

import gzip

import httpx

_FALLBACK_ENCODINGS = ("utf-8-sig", "utf-16", "cp1252")

# Some IPTV providers return a JavaScript landing page unless a more
# realistic player client is identified. The Semar endpoint is a known
# example: OTT Navigator gets the JSON payload, while the default repo's
# user agent gets an HTML redirect page instead.
_FALLBACK_USER_AGENTS = (
    "OTT Navigator/1.7.5.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)

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
        response = await self._fetch_response_with_fallback()
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
        response = await self._fetch_response_with_fallback()
        return self._maybe_decompress(response.content)

    async def _fetch_response_with_fallback(self) -> httpx.Response:
        candidates = [self._user_agent, *_FALLBACK_USER_AGENTS]
        seen: set[str] = set()
        last_response: httpx.Response | None = None

        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            for user_agent in candidates:
                if user_agent in seen:
                    continue
                seen.add(user_agent)

                headers = {"User-Agent": user_agent}
                try:
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

                last_response = response
                if not self._is_html_landing_page(response.content):
                    return response

            if last_response is not None:
                return last_response

            raise PlaylistFetchError(f"failed to fetch {self._url}: no usable response")

    @staticmethod
    def _is_html_landing_page(raw_bytes: bytes) -> bool:
        stripped = raw_bytes.lstrip()
        if not stripped:
            return False
        lower = stripped[:512].lower()
        return (
            lower.startswith(b"<!doctype html")
            or lower.startswith(b"<html")
            or b"<script" in lower
            or b'fetch("")' in lower
        )

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
