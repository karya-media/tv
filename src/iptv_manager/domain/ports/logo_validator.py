"""Port: checking whether a channel's logo image is reachable."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.logo_validation_result import LogoValidationResult


@runtime_checkable
class LogoValidator(Protocol):
    async def validate(self, channel: Channel) -> LogoValidationResult: ...
