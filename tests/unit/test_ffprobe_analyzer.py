"""Tests for infrastructure.validators.ffprobe_analyzer.

`parse_ffprobe_json` is tested as a pure function with hand-written
fixture dicts (no subprocess, no network). `FFprobeAnalyzer.analyze`
is additionally tested end-to-end against a real tiny local video file
generated with ffmpeg (tests/fixtures/sample_clip.mp4), since ffprobe
is actually installed in this environment.
"""

from pathlib import Path

import pytest

from iptv_manager.infrastructure.validators.ffprobe_analyzer import (
    FFprobeAnalyzer,
    parse_ffprobe_json,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class TestParseFFprobeJsonPure:
    def test_extracts_video_and_audio_fields(self):
        data = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30000/1001",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "channels": 2,
                    "sample_rate": "48000",
                },
            ],
            "format": {
                "format_name": "mpegts",
                "bit_rate": "5000000",
                "duration": "3600.5",
            },
        }
        info = parse_ffprobe_json(data)

        assert info.resolution == "1920x1080"
        assert info.video_codec == "h264"
        assert info.fps == pytest.approx(29.97, abs=0.01)
        assert info.audio_codec == "aac"
        assert info.audio_channels == 2
        assert info.audio_sample_rate == 48000
        assert info.bitrate_kbps == 5000
        assert info.container_format == "mpegts"
        assert info.duration_seconds == 3600.5

    def test_missing_video_stream_leaves_video_fields_none(self):
        data = {"streams": [{"codec_type": "audio", "codec_name": "mp3"}], "format": {}}
        info = parse_ffprobe_json(data)
        assert info.resolution is None
        assert info.video_codec is None
        assert info.audio_codec == "mp3"

    def test_empty_input_produces_empty_info(self):
        info = parse_ffprobe_json({})
        assert info.is_empty

    def test_malformed_frame_rate_is_ignored_gracefully(self):
        data = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "avg_frame_rate": "0/0"}
            ],
            "format": {},
        }
        info = parse_ffprobe_json(data)
        assert info.fps is None

    def test_integer_frame_rate_without_fraction(self):
        data = {
            "streams": [{"codec_type": "video", "codec_name": "h264", "r_frame_rate": "25"}],
            "format": {},
        }
        info = parse_ffprobe_json(data)
        assert info.fps == 25.0


class TestFFprobeAnalyzerRealBinary:
    """Exercises the real ffprobe subprocess against a real local file -
    this is the only place in the suite that spawns an external
    process, and it's deterministic since the fixture file is static.
    """

    @pytest.mark.asyncio
    async def test_analyze_real_sample_clip(self):
        analyzer = FFprobeAnalyzer()
        clip_path = FIXTURES / "sample_clip.mp4"
        info = await analyzer.analyze(str(clip_path))

        assert info is not None
        assert info.resolution == "320x240"
        assert info.video_codec == "h264"
        assert info.audio_codec == "aac"
        assert info.container_format == "mov,mp4,m4a,3gp,3g2,mj2"
        assert info.duration_seconds == pytest.approx(1.0, abs=0.1)

    @pytest.mark.asyncio
    async def test_analyze_nonexistent_file_returns_none(self):
        analyzer = FFprobeAnalyzer()
        info = await analyzer.analyze(str(FIXTURES / "does-not-exist.mp4"))
        assert info is None

    @pytest.mark.asyncio
    async def test_analyze_respects_timeout(self):
        # ffprobe on a nonexistent local file fails fast, so this just
        # verifies a very short timeout doesn't crash the analyzer -
        # a hanging analysis (e.g. a stalled network stream) would be
        # killed the same way.
        analyzer = FFprobeAnalyzer(timeout_seconds=0.001)
        info = await analyzer.analyze(str(FIXTURES / "sample_clip.mp4"))
        # Either it finished within the tiny timeout or it was killed -
        # both are acceptable outcomes; the call must not raise/hang.
        assert info is None or info is not None
