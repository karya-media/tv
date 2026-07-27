"""Remote URL playlist source.

Fetches a playlist over HTTP(S) using httpx, with a timeout and a
custom User-Agent (some IPTV providers reject requests with a blank or
missing User-Agent header).
"""

from __future__ import annotations

import httpx

_FALLBACK_ENCODINGS = ("utf-8-sig", "utf-16", "cp1252")


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

    def _decode(self, raw_bytes: bytes) -> str:
        for encoding in _FALLBACK_ENCODINGS:
            try:
                return raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw_bytes.decode("latin-1")
