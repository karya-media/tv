"""Stream validation result entities.

StreamStatus distinguishes *why* a stream is unreachable, because each
cause implies a different fix for the playlist maintainer: OFFLINE
means the channel is genuinely down, DNS_ERROR usually means the
domain/provider is gone entirely, SSL_ERROR often means an expired
certificate the provider needs to renew, and GEO_RESTRICTED means the
stream is fine but blocked for the validator's network location.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from iptv_manager.domain.entities.channel import Channel


class StreamStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    TIMEOUT = "timeout"
    DNS_ERROR = "dns_error"
    SSL_ERROR = "ssl_error"
    GEO_RESTRICTED = "geo_restricted"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class StreamValidationResult:
    channel: Channel
    status: StreamStatus
    http_status: int | None = None
    response_time_ms: float | None = None
    final_url: str | None = None
    redirected: bool = False
    error_message: str | None = None

    @property
    def is_online(self) -> bool:
        return self.status is StreamStatus.ONLINE
