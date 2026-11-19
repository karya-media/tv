"""Validation summary and bounded optional media analysis."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace

from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.entities.stream_validation_result import (
    StreamStatus,
    StreamValidationResult,
)
from iptv_manager.domain.ports.media_analyzer import MediaAnalyzer
from iptv_manager.domain.ports.stream_validator import StreamValidator


@dataclass(slots=True)
class StreamValidationSummary:
    results: list[StreamValidationResult] = field(default_factory=list)
    excluded_urls: set[str] = field(default_factory=set)

    @property
    def total(self) -> int:
        return len(self.results)

    def count_by_status(self, status: StreamStatus) -> int:
        return sum(1 for result in self.results if result.status is status)

    @property
    def online_count(self) -> int:
        return self.count_by_status(StreamStatus.ONLINE)

    @property
    def offline_count(self) -> int:
        return self.count_by_status(StreamStatus.OFFLINE)

    @property
    def ffprobe_count(self) -> int:
        return sum(result.media_info is not None for result in self.results)

    def filter_by_status(self, status: StreamStatus) -> list[StreamValidationResult]:
        return [result for result in self.results if result.status is status]


@dataclass(slots=True)
class ValidateStreamsUseCase:
    validator: StreamValidator
    media_analyzer: MediaAnalyzer | None = None
    analyze_online_only: bool = True

    async def execute(self, playlist: Playlist) -> StreamValidationSummary:
        results = list(await asyncio.gather(*(self.validator.validate(channel) for channel in playlist)))
        if self.media_analyzer is not None:
            async def analyze(result: StreamValidationResult) -> StreamValidationResult:
                if self.analyze_online_only and result.status is not StreamStatus.ONLINE:
                    return result
                info = await self.media_analyzer.analyze(str(result.channel.url))
                return replace(result, media_info=info)

            results = list(await asyncio.gather(*(analyze(result) for result in results)))
        return StreamValidationSummary(results=results)
