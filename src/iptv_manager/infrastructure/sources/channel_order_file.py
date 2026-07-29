"""Parser for data/channel_order.txt: an optional file letting the
user pin specific channels to specific positions in the merged master
playlist, regardless of which category file they came from.

Format (one channel display name per line, blank lines and '#'
comments ignored, order = desired priority order):

    RCTI
    SCTV
    Trans TV

Matching against Channel.name is case-insensitive and
whitespace-trimmed (so "rcti", " RCTI ", "Rcti" all match "RCTI").
If more than one channel shares a pinned name (e.g. the same channel
name appears in two source categories with different stream URLs),
all of them are pinned to that position, in their original relative
order. Channels not listed here keep their original merge order and
are placed after every pinned channel.
"""

from __future__ import annotations

from pathlib import Path


def parse_channel_order_file(path: Path) -> list[str]:
    """Read and parse a channel_order.txt file. Returns an empty list
    if the file doesn't exist (custom ordering is opt-in)."""
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8-sig")  # tolerate a BOM from Notepad etc.
    names: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        names.append(line)
    return names
