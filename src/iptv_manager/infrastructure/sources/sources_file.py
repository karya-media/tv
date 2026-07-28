"""Parser for data/sources.txt: the config file listing which
category files should be auto-synced from a remote URL on a schedule.

Format (one entry per line, blank lines and '#' comments ignored):

    dens_tv_sync=https://provider.example.com/dens_tv.m3u
    nasional_sync=https://provider.example.com/nasional.m3u

The left-hand side becomes the output filename under
data/categories/<name>.m3u (so it MUST NOT collide with a manually
maintained category file the user wants to keep untouched - that's
why the convention is to suffix synced categories with `_sync`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class SourcesFileError(ValueError):
    """Raised when a line in sources.txt is malformed."""


@dataclass(frozen=True, slots=True)
class SourceEntry:
    name: str
    url: str


def parse_sources_file(path: Path) -> list[SourceEntry]:
    """Read and parse a sources.txt file. Returns an empty list if the
    file doesn't exist (auto-sync is an opt-in feature)."""
    if not path.exists():
        return []

    entries: list[SourceEntry] = []
    text = path.read_text(encoding="utf-8-sig")  # tolerate a BOM from Notepad etc.

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            raise SourcesFileError(
                f"{path}:{line_no}: expected 'name=url', got: {raw_line!r}"
            )

        name, _, url = line.partition("=")
        name = name.strip()
        url = url.strip()

        if not name or not url:
            raise SourcesFileError(
                f"{path}:{line_no}: name and url must both be non-empty: {raw_line!r}"
            )
        if not (url.startswith("http://") or url.startswith("https://")):
            raise SourcesFileError(
                f"{path}:{line_no}: url must start with http:// or https://: {raw_line!r}"
            )
        if any(sep in name for sep in ("/", "\\", "..")):
            raise SourcesFileError(
                f"{path}:{line_no}: name must be a plain filename stem, no path separators: "
                f"{raw_line!r}"
            )

        entries.append(SourceEntry(name=name, url=url))

    return entries
