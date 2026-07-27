"""StreamUrl value object.

Wraps a channel's stream URL, guaranteeing at construction time that
it's a usable URL rather than garbage. Real-world IPTV playlists use
schemes beyond http/https (rtmp, rtsp, udp multicast, mms, srt), so all
of those are accepted.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

_ALLOWED_SCHEMES = frozenset(
    {"http", "https", "rtmp", "rtmps", "rtsp", "udp", "rtp", "mms", "srt"}
)


class InvalidStreamUrlError(ValueError):
    """Raised when a string cannot be parsed as a usable stream URL."""


@dataclass(frozen=True, slots=True)
class StreamUrl:
    raw: str
    scheme: str
    host: str | None

    @classmethod
    def parse(cls, raw: str | None) -> "StreamUrl":
        if raw is None:
            raise InvalidStreamUrlError("stream URL is missing")
        cleaned = raw.strip()
        if not cleaned:
            raise InvalidStreamUrlError("stream URL is empty")

        parsed = urlparse(cleaned)
        scheme = parsed.scheme.lower()
        if scheme not in _ALLOWED_SCHEMES:
            raise InvalidStreamUrlError(
                f"unsupported or missing URL scheme {scheme!r} in {cleaned!r}"
            )
        if not parsed.netloc:
            raise InvalidStreamUrlError(f"URL has no host: {cleaned!r}")

        return cls(raw=cleaned, scheme=scheme, host=parsed.hostname)

    @property
    def normalized_key(self) -> str:
        """Case-insensitive, trailing-slash-insensitive key used purely
        for duplicate detection. Two URLs differing only in host casing
        or a trailing slash represent the same stream."""
        parsed = urlparse(self.raw)
        path = parsed.path.rstrip("/")
        host = (parsed.hostname or "").lower()
        return f"{parsed.scheme.lower()}://{host}{path}?{parsed.query}"

    def __str__(self) -> str:
        return self.raw
