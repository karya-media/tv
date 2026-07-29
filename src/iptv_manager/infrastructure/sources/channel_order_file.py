"""Parser for data/channel_order.txt: an optional file letting the
user pin specific channels to specific positions in the merged master
playlist, regardless of which category file they came from.

Format (one priority slot per line, blank lines and '#' comments
ignored, order = desired priority order):

    RCTI
    SCTV
    Trans TV

A line may list several alternative spellings for the same slot,
separated by '|' - useful because a channel's exact display name can
vary between sources/updates (e.g. "RCTI" vs "RCTI HD" vs "RCTI.id"):

    RCTI|RCTI HD|RCTI.id
    SCTV|SCTV HD

Matching against Channel.name is case-insensitive and
whitespace-trimmed for every alternative on the line. If more than
one channel matches a slot (whether via the same alternative or
different ones), all of them are pinned to that position, in their
original relative order. Channels not listed here keep their original
merge order and are placed after every pinned channel.
"""

from __future__ import annotations

from pathlib import Path


def parse_channel_order_file(path: Path) -> list[list[str]]:
    """Read and parse a channel_order.txt file. Returns an empty list
    if the file doesn't exist (custom ordering is opt-in). Each
    returned item is the list of name alternatives for one priority
    slot (usually just one name, more if '|' was used)."""
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8-sig")  # tolerate a BOM from Notepad etc.
    slots: list[list[str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        alternatives = [alt.strip() for alt in line.split("|") if alt.strip()]
        if alternatives:
            slots.append(alternatives)
    return slots
