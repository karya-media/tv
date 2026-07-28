"""FFprobe-based media analyzer.

Shells out to `ffprobe -show_format -show_streams -print_format json`
to extract technical characteristics of a stream. This is the only
place in the codebase that spawns a subprocess for media analysis.

The JSON-parsing logic is factored into a standalone, pure function
(`parse_ffprobe_json`) so it can be unit tested without ever touching
a subprocess or a real network stream.
"""

from __future__ import annotations

import asyncio
import json

from iptv_manager.domain.entities.stream_media_info import StreamMediaInfo


class FFprobeAnalyzer:
    """Concrete implementation of domain.ports.MediaAnalyzer."""

    def __init__(
        self,
        *,
        ffprobe_binary: str = "ffprobe",
        timeout_seconds: float = 15.0,
        max_concurrency: int = 10,
    ) -> None:
        self._binary = ffprobe_binary
        self._timeout = timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def analyze(self, stream_url: str) -> StreamMediaInfo | None:
        async with self._semaphore:
            process = await asyncio.create_subprocess_exec(
                self._binary,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                stream_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, _stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self._timeout
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return None

            if process.returncode != 0 or not stdout:
                return None

            try:
                data = json.loads(stdout)
            except json.JSONDecodeError:
                return None

            return parse_ffprobe_json(data)


def parse_ffprobe_json(data: dict) -> StreamMediaInfo:
    """Pure transform: raw `ffprobe -show_format -show_streams` JSON
    output -> StreamMediaInfo. No subprocess, no I/O - fully unit
    testable with hand-written fixture dicts."""
    fmt = data.get("format") or {}
    streams = data.get("streams") or []

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    resolution = None
    fps = None
    video_codec = None
    if video_stream:
        width = video_stream.get("width")
        height = video_stream.get("height")
        if width and height:
            resolution = f"{width}x{height}"
        video_codec = video_stream.get("codec_name")
        raw_frame_rate = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
        fps = _parse_frame_rate(raw_frame_rate)

    audio_codec = audio_stream.get("codec_name") if audio_stream else None
    audio_channels = audio_stream.get("channels") if audio_stream else None
    sample_rate = _safe_int(audio_stream.get("sample_rate")) if audio_stream else None

    bitrate_kbps = _safe_int(fmt.get("bit_rate"))
    if bitrate_kbps is not None:
        bitrate_kbps = bitrate_kbps // 1000

    duration_seconds = _safe_float(fmt.get("duration"))
    container_format = fmt.get("format_name")

    return StreamMediaInfo(
        resolution=resolution,
        video_codec=video_codec,
        audio_codec=audio_codec,
        bitrate_kbps=bitrate_kbps,
        fps=fps,
        audio_channels=audio_channels,
        audio_sample_rate=sample_rate,
        container_format=container_format,
        duration_seconds=duration_seconds,
    )


def _parse_frame_rate(raw: str | None) -> float | None:
    """FFprobe reports frame rate as a fraction string like "30000/1001"."""
    if not raw:
        return None
    if "/" in raw:
        numerator, _, denominator = raw.partition("/")
        try:
            num, den = float(numerator), float(denominator)
        except ValueError:
            return None
        if den == 0:
            return None
        return round(num / den, 3)
    try:
        return float(raw)
    except ValueError:
        return None


def _safe_int(raw: str | int | None) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def _safe_float(raw: str | float | None) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None
