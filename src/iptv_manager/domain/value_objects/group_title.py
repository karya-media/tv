"""GroupTitle value object.

Normalizes a channel's group-title (its category label) so the same
category doesn't end up split across variants like "Sports",
" sports " (extra whitespace), or an empty string in the merged
playlist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WHITESPACE = re.compile(r"\s+")

DEFAULT_GROUP = "Uncategorized"


@dataclass(frozen=True, slots=True)
class GroupTitle:
    value: str

    @classmethod
    def parse(cls, raw: str | None) -> GroupTitle:
        if raw is None:
            return cls(DEFAULT_GROUP)
        cleaned = _WHITESPACE.sub(" ", raw).strip()
        return cls(cleaned) if cleaned else cls(DEFAULT_GROUP)

    def __str__(self) -> str:
        return self.value
