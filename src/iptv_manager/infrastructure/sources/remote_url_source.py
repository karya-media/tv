"""Remote URL playlist source.

Fetches a playlist over HTTP(S) using httpx with a timeout. Player
providers may vary their response by User-Agent, so the OTT Navigator
User-Agent is attempted first for every source, followed by the configured
and browser User-Agents. HTTP errors and HTML landing pages do not prevent
trying the remaining candidates.
"""

from __future__ import annotations

import gzip

import httpx

_FALLBACK_ENCODINGS = ("utf-8-sig", "utf-16", "cp1252")
_DEFAULT_USER_AGENT = "OTT Navigator/1.7.5.1"
_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_GZIP_MAGIC = b"\x1f\x8b"


class PlaylistFetchError(RuntimeError):
    """Raised when the remote playlist could not be retrieved."""


class RemoteUrlPlaylistSource:
    """Fetch a remote playlist, retrying alternate client User-Agents."""

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
        """Fetch bytes without text decoding, decompressing literal gzip."""
        response = await self._fetch_response_with_fallback()
        return self._maybe_decompress(response.content)

    async def _fetch_response_with_fallback(self) -> httpx.Response:
        # Put the known working player UA first for all configured URLs.
        candidates = (_DEFAULT_USER_AGENT, self._user_agent, _BROWSER_USER_AGENT)
        seen: set[str] = set()
        last_status: int | None = None
        last_error: httpx.HTTPError | None = None
        saw_html = False

        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            for user_agent in candidates:
                if user_agent in seen:
                    continue
                seen.add(user_agent)
                try:
                    response = await client.get(self._url, headers={"User-Agent": user_agent})
                except httpx.TimeoutException as exc:
                    # A timeout likely applies to the host/request itself;
                    # retrying the same URL with another UA won't help.
                    raise PlaylistFetchError(f"timed out fetching {self._url}") from exc
                except httpx.HTTPError as exc:
                    last_error = exc
                    continue

                if response.status_code >= 400:
                    last_status = response.status_code
                    continue
                if self._is_html_landing_page(response.content):
                    saw_html = True
                    continue
                return response

        if last_status is not None:
            raise PlaylistFetchError(f"HTTP {last_status} fetching {self._url}")
        if last_error is not None:
            raise PlaylistFetchError(f"failed to fetch {self._url}: {last_error}") from last_error
        if saw_html:
            raise PlaylistFetchError(
                f"all User-Agent responses were HTML landing pages for {self._url}"
            )
        raise PlaylistFetchError(f"failed to fetch {self._url}: no usable response")

    @staticmethod
    def _is_html_landing_page(raw_bytes: bytes) -> bool:
        prefix = raw_bytes.lstrip()[:1024].lower()
        return (
            prefix.startswith(b"<!doctype html")
            or prefix.startswith(b"<html")
            or b"<script" in prefix
            or b'fetch("")' in prefix
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
