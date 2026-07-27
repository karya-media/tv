"""Use case: validate every channel's logo image in a playlist
concurrently."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from iptv_manager.domain.entities.logo_validation_result import LogoValidationResult
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.ports.logo_validator import LogoValidator


@dataclass(slots=True)
class LogoValidationSummary:
    results: list[LogoValidationResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def missing_count(self) -> int:
        return sum(1 for r in self.results if r.error_message == "no logo_url set")

    @property
    def unreachable_count(self) -> int:
        return sum(
            1 for r in self.results if not r.reachable and r.error_message != "no logo_url set"
        )

    @property
    def reachable_count(self) -> int:
        return sum(1 for r in self.results if r.reachable)


@dataclass(slots=True)
class ValidateLogosUseCase:
    validator: LogoValidator

    async def execute(self, playlist: Playlist) -> LogoValidationSummary:
        results = await asyncio.gather(*(self.validator.validate(c) for c in playlist))
        return LogoValidationSummary(results=list(results))
