"""Logo validation result entity.

Deliberately separate from StreamValidationResult even though the
underlying HTTP check is similar: a logo failure is cosmetic (missing
artwork), not a broken channel, so report generators need to treat the
two severities differently.
"""

from __future__ import annotations

from dataclasses import dataclass

from iptv_manager.domain.entities.channel import Channel


@dataclass(frozen=True, slots=True)
class LogoValidationResult:
    channel: Channel
    reachable: bool
    http_status: int | None = None
    error_message: str | None = None

    @classmethod
    def missing(cls, channel: Channel) -> LogoValidationResult:
        """The channel has no logo_url at all - distinct from having one
        that's unreachable."""
        return cls(channel=channel, reachable=False, error_message="no logo_url set")
