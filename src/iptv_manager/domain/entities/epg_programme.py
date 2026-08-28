"""EPGProgramme entity.

Represents one <programme> element from an XMLTV file: a single
scheduled broadcast (start/stop time, title, and optionally a
description/category) on one channel.

Timestamps are kept as the raw XMLTV string (e.g.
"20260827120000 +0700") rather than parsed into datetime objects -
every consumer of a merged EPG file (IPTV players, this project's own
writer) speaks that exact format natively, so parsing and immediately
re-serializing it would be pure overhead with no benefit, and risks
timezone-conversion bugs for no reason.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EPGProgramme:
    channel_id: str
    start: str
    stop: str | None
    title: str
    description: str | None = None
    category: str | None = None
