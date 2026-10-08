"""Shared helper for Excel (.xlsx) writers.

Real-world IPTV source data is noisy - control characters occasionally
show up in a channel name, group-title, or other free-text field
(seen in the wild alongside things like emoji, superscripts, and
malformed attributes elsewhere in this project's category files).
openpyxl raises IllegalCharacterError if asked to write a string
containing one of these to a cell, since the underlying .xlsx format
is XML and a handful of ASCII control characters are simply not legal
XML content, in any encoding or escaping.

sanitize_for_excel() strips exactly those characters (the same set
openpyxl's own openpyxl.cell.cell.ILLEGAL_CHARACTERS_RE flags) before
a value ever reaches a cell, so a channel with one stray control
character in its name doesn't take down the whole export - used by
every writer in infrastructure.reports/ that puts free-text values
into cells.
"""

from __future__ import annotations

from typing import Any

from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE


def sanitize_for_excel(value: Any) -> Any:  # noqa: ANN401 - passes non-str values through untouched
    """Strip XML-illegal control characters from a string before it's
    written to a cell. Non-string values (numbers, None, ...) are
    returned unchanged - only text can carry an illegal character."""
    if not isinstance(value, str):
        return value
    return ILLEGAL_CHARACTERS_RE.sub("", value)
