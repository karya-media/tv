"""Port: turning raw XMLTV text into domain EPGChannel entities.

infrastructure.parsers.XMLTVParser is the concrete implementation
(uses lxml). Kept separate from PlaylistParser since the two formats
(M3U vs XMLTV) have nothing in common beyond both being text-based.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from iptv_manager.domain.entities.epg_channel import EPGChannel


@runtime_checkable
class EPGParser(Protocol):
    def parse(self, raw_text: str) -> list[EPGChannel]: ...
