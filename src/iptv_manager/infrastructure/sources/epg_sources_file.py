"""Parser for data/epg_sources.txt: the list of XMLTV EPG source URLs
`iptv-manager merge-epg` combines into one file (see
MergeEPGSourcesUseCase).

Format (one URL per line, blank lines and '#' comments ignored, order
matters - earlier entries take priority when two sources define the
same channel or programme):

    https://provider-one.example.com/epg.xml.gz
    # a comment explaining the next source
    https://provider-two.example.com/epg.xml
"""

from __future__ import annotations

from pathlib import Path


def parse_epg_sources_file(path: Path) -> list[str]:
    """Read and parse an epg_sources.txt file. Returns an empty list
    if the file doesn't exist (EPG merging is opt-in)."""
    if not path.exists():
        return []

    urls: list[str] = []
    text = path.read_text(encoding="utf-8-sig")  # tolerate a BOM from Notepad etc.
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls
