"""EPGChannel entity.

Represents one <channel> element from an XMLTV file: its id (the value
that should match a playlist's tvg-id) and its display name(s)/icon,
used only for reporting (so a report can show a human-readable name
next to a raw EPG id).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EPGChannel:
    id: str
    display_names: tuple[str, ...] = field(default_factory=tuple)
    icon_url: str | None = None

    @property
    def primary_display_name(self) -> str | None:
        return self.display_names[0] if self.display_names else None
