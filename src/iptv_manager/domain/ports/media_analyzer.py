"""Port: extracting technical media info from a stream URL (FFprobe).

infrastructure.validators.FFprobeAnalyzer is the concrete
implementation, isolating the only place in the codebase that shells
out to a subprocess.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from iptv_manager.domain.entities.stream_media_info import StreamMediaInfo


@runtime_checkable
class MediaAnalyzer(Protocol):
    async def analyze(self, stream_url: str) -> StreamMediaInfo | None:
        """Return media characteristics, or None if analysis failed
        (unreachable stream, FFprobe timeout, unrecognized container).
        Never raises for a bad/unreachable stream - that's an expected
        outcome, not an exceptional one."""
        ...
