"""Use case: validate every channel's stream in a playlist concurrently.

Concurrency is bounded by the validator itself (HttpStreamValidator
owns its own semaphore), so this use case just fans requests out with
asyncio.gather and doesn't need to manage concurrency directly.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.entities.stream_validation_result import (
    StreamStatus,
    StreamValidationResult,
)
from iptv_manager.domain.ports.stream_validator import StreamValidator


@dataclass(slots=True)
class StreamValidationSummary:
    results: list[StreamValidationResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    def count_by_status(self, status: StreamStatus) -> int:
        return sum(1 for r in self.results if r.status is status)

    @property
    def online_count(self) -> int:
        return self.count_by_status(StreamStatus.ONLINE)

    @property
    def offline_count(self) -> int:
        return self.total - self.online_count

    def filter_by_status(self, status: StreamStatus) -> list[StreamValidationResult]:
        return [r for r in self.results if r.status is status]


@dataclass(slots=True)
class ValidateStreamsUseCase:
    validator: StreamValidator

    async def execute(self, playlist: Playlist) -> StreamValidationSummary:
        results = await asyncio.gather(
            *(self.validator.validate(channel) for channel in playlist)
        )
        return StreamValidationSummary(results=list(results))
