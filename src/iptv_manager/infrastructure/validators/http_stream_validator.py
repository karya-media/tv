"""HTTP stream validator that verifies headers and actual stream bytes.

HEAD is used as a cheap preliminary check, but a successful HEAD is never
considered proof of playability: a bounded Range GET must return readable,
non-HTML bytes. Each retry is a separate request with a short backoff.
"""

from __future__ import annotations

import asyncio
import errno
import ssl
import time

import aiohttp

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.stream_validation_result import (
    StreamStatus,
    StreamValidationResult,
)

_GEO_RESTRICTED_STATUSES = frozenset({403})
_PROBE_CHUNK_BYTES = 1024
_STREAM_CONTENT_TYPES = (
    "video/", "audio/", "application/octet-stream", "application/mp2t",
    "application/vnd.apple.mpegurl", "application/x-mpegurl", "application/mpegurl",
    "application/ogg", "application/x-flv", "application/vnd.rn-realmedia",
)
_HTML_PREFIXES = (b"<!doctype html", b"<html", b"<head", b"<body")


class HttpStreamValidator:
    """Concrete implementation of domain.ports.StreamValidator."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        max_concurrency: int = 50,
        user_agent: str = "IPTV-Playlist-Manager/0.1",
        retries: int = 1,
        retry_delay_seconds: float = 0.25,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._user_agent = user_agent
        self._retries = max(1, retries)
        self._retry_delay = max(0.0, retry_delay_seconds)

    async def validate(self, channel: Channel) -> StreamValidationResult:
        async with self._semaphore:
            result: StreamValidationResult | None = None
            for attempt in range(self._retries):
                result = await self._validate_once(channel)
                if result.is_online or result.status is StreamStatus.GEO_RESTRICTED:
                    return result
                if attempt + 1 < self._retries and self._retry_delay:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
            assert result is not None
            return result

    def _headers(self, channel: Channel) -> dict[str, str]:
        headers = {"User-Agent": self._user_agent, "Range": f"bytes=0-{_PROBE_CHUNK_BYTES - 1}"}
        # Preserve headers represented by the M3U #EXTVLCOPT directives.
        known = {
            "http-user-agent": "User-Agent",
            "http-referrer": "Referer",
            "http-referer": "Referer",
            "http-origin": "Origin",
            "http-cookie": "Cookie",
        }
        for key, value in channel.vlc_opts.items():
            header = known.get(key.lower())
            if header and value.strip():
                headers[header] = value.strip()
        return headers

    async def _validate_once(self, channel: Channel) -> StreamValidationResult:
        url = str(channel.url)
        headers = self._headers(channel)
        async with aiohttp.ClientSession(timeout=self._timeout, headers=headers) as session:
            try:
                async with session.head(url, allow_redirects=True) as response:
                    if response.status in _GEO_RESTRICTED_STATUSES:
                        return self._result(channel, response, 0.0, StreamStatus.GEO_RESTRICTED)
                    # HEAD status can identify clear permanent HTTP failures. For
                    # success/unsupported HEAD, GET is still required to prove bytes flow.
                    if response.status in (404, 410):
                        return self._result(channel, response, 0.0, StreamStatus.OFFLINE)
                    if response.status not in (405, 501) and not 200 <= response.status < 300:
                        return self._result(channel, response, 0.0, StreamStatus.ERROR)
            except (aiohttp.ClientError, TimeoutError, ssl.SSLError):
                # GET provides the authoritative result/classification and may
                # work even when a server rejects HEAD.
                pass
            return await self._get_stream(session, channel, url)

    async def _get_stream(
        self, session: aiohttp.ClientSession, channel: Channel, url: str
    ) -> StreamValidationResult:
        start = time.monotonic()
        try:
            async with session.get(url, allow_redirects=True) as response:
                elapsed = (time.monotonic() - start) * 1000
                status = response.status
                if status in _GEO_RESTRICTED_STATUSES:
                    return self._result(channel, response, elapsed, StreamStatus.GEO_RESTRICTED)
                if status in (404, 410):
                    return self._result(channel, response, elapsed, StreamStatus.OFFLINE)
                if status < 200 or status >= 300:
                    return self._result(channel, response, elapsed, StreamStatus.ERROR)
                try:
                    data = await asyncio.wait_for(
                        response.content.read(_PROBE_CHUNK_BYTES), timeout=self._timeout_seconds
                    )
                except (TimeoutError, aiohttp.ClientPayloadError) as exc:
                    return self._result(
                        channel, response, elapsed, StreamStatus.TIMEOUT,
                        error=str(exc) or "no stream data received before timeout",
                    )
                if not data:
                    return self._result(
                        channel, response, elapsed, StreamStatus.ERROR, error="empty stream response"
                    )
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if self._looks_like_error_page(data, content_type):
                    return self._result(
                        channel, response, elapsed, StreamStatus.ERROR,
                        error=f"non-stream response (content-type: {content_type or 'unknown'})",
                        bytes_read=len(data),
                    )
                return self._result(
                    channel, response, elapsed, StreamStatus.ONLINE, bytes_read=len(data)
                )
        except TimeoutError as exc:
            return StreamValidationResult(channel=channel, status=StreamStatus.TIMEOUT,
                                          error_message=str(exc) or "request timed out")
        except (aiohttp.ClientConnectorCertificateError, aiohttp.ClientSSLError, ssl.SSLError) as exc:
            return StreamValidationResult(channel=channel, status=StreamStatus.SSL_ERROR,
                                          error_message=str(exc))
        except aiohttp.ClientConnectorDNSError as exc:
            return StreamValidationResult(channel=channel, status=StreamStatus.DNS_ERROR,
                                          error_message=str(exc))
        except aiohttp.ClientConnectorError as exc:
            if isinstance(exc.os_error, OSError) and exc.os_error.errno in (
                errno.EAI_NONAME if hasattr(errno, "EAI_NONAME") else -2,
                errno.EAI_AGAIN if hasattr(errno, "EAI_AGAIN") else -3,
            ):
                return StreamValidationResult(channel=channel, status=StreamStatus.DNS_ERROR,
                                              error_message=str(exc))
            return StreamValidationResult(channel=channel, status=StreamStatus.OFFLINE,
                                          error_message=str(exc))
        except aiohttp.ClientError as exc:
            return StreamValidationResult(channel=channel, status=StreamStatus.ERROR,
                                          error_message=str(exc))

    @staticmethod
    def _looks_like_error_page(data: bytes, content_type: str) -> bool:
        if content_type in ("text/html", "application/xhtml+xml", "application/json"):
            return True
        prefix = data.lstrip().lower()[:64]
        return prefix.startswith(_HTML_PREFIXES)

    @staticmethod
    def _result(
        channel: Channel,
        response: aiohttp.ClientResponse,
        elapsed_ms: float,
        status: StreamStatus,
        *,
        error: str | None = None,
        bytes_read: int = 0,
    ) -> StreamValidationResult:
        return StreamValidationResult(
            channel=channel,
            status=status,
            http_status=response.status,
            response_time_ms=round(elapsed_ms, 1),
            final_url=str(response.url),
            redirected=bool(response.history),
            error_message=error,
            content_type=response.headers.get("Content-Type"),
            bytes_read=bytes_read,
        )
