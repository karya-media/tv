"""Parser for data/playlists.txt: an optional config file letting the
user define multiple named playlist "bundles", each publishing a
different subset of channels to its own file/URL.

Why this exists: a single merged master.m3u containing every category
(including large, loosely-curated auto-synced sources) can grow to
tens of thousands of channels. Many IPTV player apps cap how many
channels they'll load, or simply become slow/unreliable with very
large playlists. Splitting into bundles lets the user keep a small,
reliable "everyday" link while still publishing a "everything" link
for anyone who wants the full set.

Format (one bundle per line: name=comma,separated,entries):

    master=01-nasional,02-olahraga,03-dens_tv,beetv
    indonesia=group:Indonesia
    everything_but_sports=01-nasional,group:United States,group:Germany

Each comma-separated entry is one of:
  - A category stem: a data/categories/<stem>.m3u filename without the
    extension - every channel from that whole file is included.
  - "group:<prefix>": every channel anywhere (regardless of which
    category file it came from) whose group-title is exactly <prefix>
    or starts with "<prefix>;" is included - e.g. "group:Indonesia"
    matches "Indonesia;Nasional", "Indonesia;Lokal", etc. Matching is
    case-insensitive and segment-based (so "group:Indonesia" does NOT
    match a hypothetical "IndonesiaXYZ;...").

The two kinds can be freely mixed within one bundle line; a channel
matched by both a stem and a group prefix is only included once.

Whitespace around commas is ignored.

If this file doesn't exist (or is empty), the caller should fall back
to the historical single-bundle behavior: one bundle named "master"
containing every category file. That keeps existing setups (and their
existing master.m3u URL) working unchanged with zero configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

_GROUP_PREFIX_MARKER = "group:"


class PlaylistBundlesFileError(ValueError):
    """Raised when a line in playlists.txt is malformed."""


@dataclass(frozen=True)
class PlaylistBundle:
    stems: list[str] = field(default_factory=list)
    group_prefixes: list[str] = field(default_factory=list)


def parse_playlist_bundles_file(path: Path) -> dict[str, PlaylistBundle]:
    """Read and parse a playlists.txt file. Returns an empty dict if
    the file doesn't exist or has no entries (caller applies the
    single-bundle-with-everything default in that case)."""
    if not path.exists():
        return {}

    bundles: dict[str, PlaylistBundle] = {}
    text = path.read_text(encoding="utf-8-sig")  # tolerate a BOM from Notepad etc.

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            raise PlaylistBundlesFileError(
                f"{path}:{line_no}: expected 'bundle_name=stem1,group:prefix,...', "
                f"got: {raw_line!r}"
            )

        name, _, entries_raw = line.partition("=")
        name = name.strip()
        entries = [e.strip() for e in entries_raw.split(",") if e.strip()]

        if not name:
            raise PlaylistBundlesFileError(f"{path}:{line_no}: bundle name is empty: {raw_line!r}")
        if any(sep in name for sep in ("/", "\\", "..")):
            raise PlaylistBundlesFileError(
                f"{path}:{line_no}: bundle name must be a plain filename stem: {raw_line!r}"
            )
        if not entries:
            raise PlaylistBundlesFileError(
                f"{path}:{line_no}: bundle {name!r} lists no entries: {raw_line!r}"
            )
        if name in bundles:
            raise PlaylistBundlesFileError(f"{path}:{line_no}: duplicate bundle name {name!r}")

        stems: list[str] = []
        group_prefixes: list[str] = []
        for entry in entries:
            if entry.lower().startswith(_GROUP_PREFIX_MARKER):
                prefix = entry[len(_GROUP_PREFIX_MARKER) :].strip()
                if not prefix:
                    raise PlaylistBundlesFileError(
                        f"{path}:{line_no}: bundle {name!r} has an empty 'group:' prefix: "
                        f"{raw_line!r}"
                    )
                group_prefixes.append(prefix)
            else:
                stems.append(entry)

        bundles[name] = PlaylistBundle(stems=stems, group_prefixes=group_prefixes)

    return bundles
