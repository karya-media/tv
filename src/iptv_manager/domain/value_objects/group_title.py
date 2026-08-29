"""GroupTitle value object.

Normalizes a channel's group-title (its category label) so the same
category doesn't end up split across variants like "Sports",
" sports " (extra whitespace), an empty string, an emoji-prefixed
label, a duplicated ";"-separated segment, or a meaningless
placeholder like "Undefined"/"General" in the merged playlist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WHITESPACE = re.compile(r"\s+")

# Common pictographic/symbol ranges seen prefixed onto source group-titles
# (e.g. "📺 Nasional", "🔓 Dens TV", "🔭 CCTV").
_EMOJI = re.compile(
    "["
    "\U0001f300-\U0001faff"
    "\U00002600-\U000027bf"
    "\U0001f1e6-\U0001f1ff"
    "]+"
)

DEFAULT_GROUP = "Uncategorized"

# Placeholder labels from upstream sources that carry no real category
# information and should collapse to DEFAULT_GROUP instead of being kept
# verbatim.
_FALLBACK_LABELS = {"undefined", "general", "unknown", "n/a", "-", "none"}


@dataclass(frozen=True, slots=True)
class GroupTitle:
    value: str

    @classmethod
    def parse(cls, raw: str | None) -> GroupTitle:
        if raw is None:
            return cls(DEFAULT_GROUP)

        cleaned = _EMOJI.sub("", raw)
        cleaned = _WHITESPACE.sub(" ", cleaned).strip()
        cleaned = cleaned.strip(" ;")

        if ";" in cleaned:
            cleaned = cls._dedupe_segments(cleaned)

        if not cleaned or cleaned.lower() in _FALLBACK_LABELS:
            return cls(DEFAULT_GROUP)

        return cls(cleaned)

    @staticmethod
    def _dedupe_segments(value: str) -> str:
        """Collapse repeated ';'-separated segments, preserving order.

        "Indonesia;Lainnya;Lainnya" -> "Indonesia;Lainnya"
        """
        seen: list[str] = []
        for part in value.split(";"):
            part = part.strip()
            if part and part not in seen:
                seen.append(part)
        return ";".join(seen)

    def __str__(self) -> str:
        return self.value

    def matches_prefix(self, prefix: str) -> bool:
        """True if this group-title is exactly `prefix`, or starts
        with `prefix` followed by a ";" segment boundary - matching
        case-insensitively. Segment-based so "Indonesia" matches
        "Indonesia;Nasional" but not a hypothetical "IndonesiaXYZ;...".
        Used by data/playlists.txt's "group:<prefix>" bundle entries.
        """
        normalized_value = self.value.casefold()
        normalized_prefix = prefix.strip().casefold()
        if not normalized_prefix:
            return False
        return normalized_value == normalized_prefix or normalized_value.startswith(
            f"{normalized_prefix};"
        )
