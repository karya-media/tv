"""Results from an HTTP and optional media-level stream validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.stream_media_info import StreamMediaInfo


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
    content_type: str | None = None
    bytes_read: int = 0
    media_info: StreamMediaInfo | None = None

    @property
    def is_online(self) -> bool:
        return self.status is StreamStatus.ONLINE
