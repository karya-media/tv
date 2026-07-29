"""Parser for data/playlists.txt: an optional config file letting the
user define multiple named playlist "bundles", each publishing a
different subset of data/categories/*.m3u to its own file/URL.

Why this exists: a single merged master.m3u containing every category
(including large, loosely-curated auto-synced sources) can grow to
tens of thousands of channels. Many IPTV player apps cap how many
channels they'll load, or simply become slow/unreliable with very
large playlists. Splitting into bundles lets the user keep a small,
reliable "everyday" link while still publishing a "everything" link
for anyone who wants the full set.

Format (one bundle per line: name=comma,separated,category,stems):

    master=01-nasional,02-olahraga,03-dens_tv,beetv
    full=01-nasional,02-olahraga,03-dens_tv,beetv,iptv_indonesia,itz_play

A "category stem" is a data/categories/<stem>.m3u filename without the
extension. Whitespace around commas is ignored.

If this file doesn't exist (or is empty), the caller should fall back
to the historical single-bundle behavior: one bundle named "master"
containing every category file. That keeps existing setups (and their
existing master.m3u URL) working unchanged with zero configuration.
"""

from __future__ import annotations

from pathlib import Path


class PlaylistBundlesFileError(ValueError):
    """Raised when a line in playlists.txt is malformed."""


def parse_playlist_bundles_file(path: Path) -> dict[str, list[str]]:
    """Read and parse a playlists.txt file. Returns an empty dict if
    the file doesn't exist or has no entries (caller applies the
    single-bundle-with-everything default in that case)."""
    if not path.exists():
        return {}

    bundles: dict[str, list[str]] = {}
    text = path.read_text(encoding="utf-8-sig")  # tolerate a BOM from Notepad etc.

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            raise PlaylistBundlesFileError(
                f"{path}:{line_no}: expected 'bundle_name=stem1,stem2,...', got: {raw_line!r}"
            )

        name, _, stems_raw = line.partition("=")
        name = name.strip()
        stems = [s.strip() for s in stems_raw.split(",") if s.strip()]

        if not name:
            raise PlaylistBundlesFileError(f"{path}:{line_no}: bundle name is empty: {raw_line!r}")
        if any(sep in name for sep in ("/", "\\", "..")):
            raise PlaylistBundlesFileError(
                f"{path}:{line_no}: bundle name must be a plain filename stem: {raw_line!r}"
            )
        if not stems:
            raise PlaylistBundlesFileError(
                f"{path}:{line_no}: bundle {name!r} lists no category stems: {raw_line!r}"
            )
        if name in bundles:
            raise PlaylistBundlesFileError(
                f"{path}:{line_no}: duplicate bundle name {name!r}"
            )

        bundles[name] = stems

    return bundles
