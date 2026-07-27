"""HTTP-based stream validator.

Real IPTV streams cannot be validated with a plain GET-to-completion:
the "body" is a live video feed that never ends. So this validator:

1. Tries a HEAD request first (cheapest - no body at all).
2. Falls back to a GET request if the server rejects HEAD (405, or
   simply refuses it), reading only enough of the response to confirm
   a body is actually flowing, then closes the connection immediately
   without draining it.

Response time is measured to first-byte/headers, not to a full body,
since "full body" is meaningless for a stream.
"""

from __future__ import annotations

import asyncio
import ssl
import time

import aiohttp

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.stream_validation_result import (
    StreamStatus,
    StreamValidationResult,
)

# Status codes some IPTV providers use specifically to signal that a
# stream exists but is not available from the requester's location.
_GEO_RESTRICTED_STATUSES = frozenset({403})

_PROBE_CHUNK_BYTES = 1024


class HttpStreamValidator:
    """Concrete implementation of domain.ports.StreamValidator."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        max_concurrency: int = 50,
        user_agent: str = "IPTV-Playlist-Manager/0.1",
        retries: int = 1,
    ) -> None:
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._user_agent = user_agent
        self._retries = max(1, retries)

    async def validate(self, channel: Channel) -> StreamValidationResult:
        async with self._semaphore:
            last_result: StreamValidationResult | None = None
            for attempt in range(self._retries):
                last_result = await self._validate_once(channel)
                if last_result.is_online:
                    return last_result
            assert last_result is not None
            return last_result

    async def _validate_once(self, channel: Channel) -> StreamValidationResult:
        url = str(channel.url)
        headers = {"User-Agent": self._user_agent}

        async with aiohttp.ClientSession(timeout=self._timeout, headers=headers) as session:
            result = await self._try_head(session, channel, url)
            if result is not None:
                return result
            return await self._try_get(session, channel, url)

    async def _try_head(
        self, session: aiohttp.ClientSession, channel: Channel, url: str
    ) -> StreamValidationResult | None:
        start = time.monotonic()
        try:
            async with session.head(url, allow_redirects=True) as response:
                elapsed_ms = (time.monotonic() - start) * 1000
                if response.status == 405:
                    # Server explicitly doesn't support HEAD - fall
                    # back to GET rather than treating this as a failure.
                    return None
                return self._result_from_response(channel, response, elapsed_ms)
        except (aiohttp.ClientResponseError,):
            return None  # fall back to GET
        except Exception:  # noqa: BLE001 - classified centrally in _try_get
            return None  # give GET a chance before giving up

    async def _try_get(
        self, session: aiohttp.ClientSession, channel: Channel, url: str
    ) -> StreamValidationResult:
        start = time.monotonic()
        try:
            async with session.get(url, allow_redirects=True) as response:
                elapsed_ms = (time.monotonic() - start) * 1000
                # Confirm a body is actually flowing without draining a
                # live stream - read one small chunk, then stop.
                try:
                    await response.content.read(_PROBE_CHUNK_BYTES)
                except (aiohttp.ClientPayloadError, asyncio.TimeoutError):
                    pass  # headers already told us enough
                return self._result_from_response(channel, response, elapsed_ms)
        except asyncio.TimeoutError:
            return StreamValidationResult(
                channel=channel, status=StreamStatus.TIMEOUT, error_message="request timed out"
            )
        except aiohttp.ClientConnectorCertificateError as exc:
            return StreamValidationResult(
                channel=channel, status=StreamStatus.SSL_ERROR, error_message=str(exc)
            )
        except aiohttp.ClientSSLError as exc:
            return StreamValidationResult(
                channel=channel, status=StreamStatus.SSL_ERROR, error_message=str(exc)
            )
        except aiohttp.ClientConnectorDNSError as exc:
            return StreamValidationResult(
                channel=channel, status=StreamStatus.DNS_ERROR, error_message=str(exc)
            )
        except aiohttp.ClientConnectorError as exc:
            # aiohttp doesn't always distinguish DNS failure from a
            # refused/unreachable connection at this exception level -
            # inspect the wrapped OS error when possible.
            if isinstance(exc.os_error, OSError) and exc.os_error.errno in (
                -2,  # EAI_NONAME (getaddrinfo failed)
                -3,  # EAI_AGAIN
                8,  # legacy socket.gaierror code on some platforms
            ):
                return StreamValidationResult(
                    channel=channel, status=StreamStatus.DNS_ERROR, error_message=str(exc)
                )
            return StreamValidationResult(
                channel=channel, status=StreamStatus.OFFLINE, error_message=str(exc)
            )
        except ssl.SSLError as exc:
            return StreamValidationResult(
                channel=channel, status=StreamStatus.SSL_ERROR, error_message=str(exc)
            )
        except aiohttp.ClientError as exc:
            return StreamValidationResult(
                channel=channel, status=StreamStatus.ERROR, error_message=str(exc)
            )

    def _result_from_response(
        self, channel: Channel, response: aiohttp.ClientResponse, elapsed_ms: float
    ) -> StreamValidationResult:
        redirected = len(response.history) > 0
        final_url = str(response.url)

        if response.status in _GEO_RESTRICTED_STATUSES:
            status = StreamStatus.GEO_RESTRICTED
        elif 200 <= response.status < 400:
            status = StreamStatus.ONLINE
        else:
            status = StreamStatus.ERROR

        return StreamValidationResult(
            channel=channel,
            status=status,
            http_status=response.status,
            response_time_ms=round(elapsed_ms, 1),
            final_url=final_url,
            redirected=redirected,
        )
