"""TvgId value object.

Encapsulates what makes a tvg-id well-formed and how it's normalized,
so parsers, validators, and use cases never re-implement this rule in
more than one place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

_VALID_CHARS = re.compile(r"^[A-Za-z0-9._-]+$")
_STRIP_INVALID = re.compile(r"[^A-Za-z0-9._-]")


@dataclass(frozen=True, slots=True)
class TvgId:
    """A normalized tvg-id.

    Empty/whitespace-only input is not an error - it means "no tvg-id
    was provided", represented by `TvgId.EMPTY` (value == ""). Callers
    should check `.is_present` rather than the truthiness of the object
    itself (a frozen dataclass instance is always truthy).
    """

    value: str

    EMPTY: ClassVar["TvgId"]

    @classmethod
    def parse(cls, raw: str | None) -> "TvgId":
        if raw is None:
            return cls.EMPTY
        cleaned = raw.strip()
        if not cleaned:
            return cls.EMPTY
        if not _VALID_CHARS.match(cleaned):
            # Repair: strip characters that aren't allowed instead of
            # discarding the whole channel over one bad attribute.
            cleaned = _STRIP_INVALID.sub("", cleaned)
        return cls(cleaned) if cleaned else cls.EMPTY

    @property
    def is_present(self) -> bool:
        return bool(self.value)

    def __str__(self) -> str:
        return self.value


TvgId.EMPTY = TvgId("")
