"""Stream media info entity.

Holds the technical characteristics of a stream as extracted by
FFprobe. All fields are optional because a live stream, a corrupted
container, or an FFprobe timeout can each leave individual fields
unknown without that being a hard failure - partial information is
still useful for a report.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StreamMediaInfo:
    resolution: str | None = None  # e.g. "1920x1080"
    video_codec: str | None = None
    audio_codec: str | None = None
    bitrate_kbps: int | None = None
    fps: float | None = None
    audio_channels: int | None = None
    audio_sample_rate: int | None = None
    container_format: str | None = None
    duration_seconds: float | None = None

    @property
    def is_empty(self) -> bool:
        return all(
            value is None
            for value in (
                self.resolution,
                self.video_codec,
                self.audio_codec,
                self.bitrate_kbps,
                self.fps,
                self.audio_channels,
                self.audio_sample_rate,
                self.container_format,
                self.duration_seconds,
            )
        )
