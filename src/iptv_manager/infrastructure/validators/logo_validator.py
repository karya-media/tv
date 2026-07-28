"""Logo validator.

Checks whether a channel's tvg-logo URL actually resolves to
something, using a plain HEAD (logos are small static images, so
there's no need for the stream validator's GET-fallback probing
dance).
"""

from __future__ import annotations

import asyncio

import aiohttp

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.logo_validation_result import LogoValidationResult


class LogoImageValidator:
    """Concrete implementation of domain.ports.LogoValidator."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 8.0,
        max_concurrency: int = 50,
        user_agent: str = "IPTV-Playlist-Manager/0.1",
    ) -> None:
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._user_agent = user_agent

    async def validate(self, channel: Channel) -> LogoValidationResult:
        if not channel.has_logo:
            return LogoValidationResult.missing(channel)

        async with self._semaphore:
            headers = {"User-Agent": self._user_agent}
            try:
                async with aiohttp.ClientSession(
                    timeout=self._timeout, headers=headers
                ) as session:
                    async with session.head(channel.logo_url, allow_redirects=True) as response:
                        if response.status == 405:
                            # Some image hosts reject HEAD; fall back to GET.
                            return await self._validate_via_get(session, channel)
                        return LogoValidationResult(
                            channel=channel,
                            reachable=200 <= response.status < 400,
                            http_status=response.status,
                        )
            except aiohttp.ClientError as exc:
                return LogoValidationResult(
                    channel=channel, reachable=False, error_message=str(exc)
                )
            except TimeoutError:
                return LogoValidationResult(
                    channel=channel, reachable=False, error_message="request timed out"
                )

    async def _validate_via_get(
        self, session: aiohttp.ClientSession, channel: Channel
    ) -> LogoValidationResult:
        try:
            async with session.get(channel.logo_url, allow_redirects=True) as response:
                return LogoValidationResult(
                    channel=channel,
                    reachable=200 <= response.status < 400,
                    http_status=response.status,
                )
        except aiohttp.ClientError as exc:
            return LogoValidationResult(channel=channel, reachable=False, error_message=str(exc))
        except TimeoutError:
            return LogoValidationResult(
                channel=channel, reachable=False, error_message="request timed out"
            )
