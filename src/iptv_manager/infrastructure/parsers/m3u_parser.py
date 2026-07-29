"""M3U/M3U8 parser and serializer.

Handles the real-world messiness of IPTV playlists: UTF-8 with or
without a BOM, CRLF/LF/CR line endings, a missing #EXTM3U header,
#EXTINF attributes in any order and with single or double quotes,
#EXTINF lines with a missing/malformed display name, and HTML-entity
encoded URLs/attribute values (e.g. some playlist exporters emit
"&amp;" instead of "&" in a stream URL's query string, which silently
breaks the stream unless unescaped). A single bad line never aborts
parsing of the whole file - it's repaired where possible, or skipped
with a warning recorded on the resulting Playlist.
"""

from __future__ import annotations

import html
import re

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.group_title import GroupTitle
from iptv_manager.domain.value_objects.stream_url import InvalidStreamUrlError, StreamUrl
from iptv_manager.domain.value_objects.tvg_id import TvgId

_EXTINF_RE = re.compile(
    r"""^\#EXTINF:\s*
        (?P<duration>-?\d+(?:\.\d+)?)
        (?P<attrs>(?:\s+[\w-]+=(?:"[^"]*"|'[^']*'))*)
        \s*,\s*
        (?P<name>.*)$
    """,
    re.VERBOSE,
)
_ATTR_RE = re.compile(r"""([\w-]+)=(?:"([^"]*)"|'([^']*)')""")
_VLCOPT_RE = re.compile(r"^\#EXTVLCOPT:\s*([\w-]+)=(.*)$")

# Attributes modeled explicitly on Channel; anything else in an
# #EXTINF line is preserved in Channel.extra_attrs so no metadata is
# silently dropped on merge/re-serialization.
_KNOWN_ATTRS = frozenset({"tvg-id", "tvg-name", "tvg-logo", "group-title"})


class M3UParser:
    """Concrete implementation of domain.ports.PlaylistParser."""

    def parse(self, raw_text: str, *, name: str, category: str | None = None) -> Playlist:
        playlist = Playlist(name=name, category=category)
        text = raw_text.lstrip("\ufeff")  # strip BOM if it made it this far
        lines = text.split("\n")

        saw_header = False
        pending_extinf: dict | None = None
        pending_vlc_opts: dict[str, str] = {}

        for line_no, raw_line in enumerate(lines, start=1):
            line = raw_line.strip("\r").strip()
            if not line:
                continue

            if line.startswith("#EXTM3U"):
                saw_header = True
                continue

            if line.startswith("#EXTINF"):
                match = _EXTINF_RE.match(line)
                if not match:
                    playlist.warnings.append(
                        f"line {line_no}: malformed #EXTINF, entry skipped: {line!r}"
                    )
                    pending_extinf = None
                    pending_vlc_opts = {}
                    continue
                pending_extinf = self._parse_extinf(match)
                pending_vlc_opts = {}
                continue

            if line.startswith("#EXTVLCOPT"):
                # e.g. #EXTVLCOPT:http-user-agent=Mozilla/5.0 ...
                # or   #EXTVLCOPT:http-referrer=https://example.com/
                # Many providers reject requests missing these headers,
                # so they're captured and reattached to the channel
                # rather than being dropped as an unknown directive.
                vlc_match = _VLCOPT_RE.match(line)
                if vlc_match and pending_extinf is not None:
                    key = vlc_match.group(1).lower()
                    value = html.unescape(vlc_match.group(2).strip())
                    pending_vlc_opts[key] = value
                else:
                    playlist.warnings.append(
                        f"line {line_no}: #EXTVLCOPT with no preceding #EXTINF "
                        f"or malformed, ignored: {line!r}"
                    )
                continue

            if line.startswith("#"):
                # Other directives (#EXTGRP, #EXTALB, ...) aren't
                # modeled yet - safely ignored rather than treated as
                # an error.
                continue

            # A non-comment, non-empty line is the stream URL.
            if pending_extinf is None:
                playlist.warnings.append(
                    f"line {line_no}: stream URL with no preceding #EXTINF, "
                    f"entry skipped: {line!r}"
                )
                continue

            channel = self._build_channel(
                pending_extinf, line, category, line_no, playlist.warnings, pending_vlc_opts
            )
            pending_extinf = None
            pending_vlc_opts = {}
            if channel is not None:
                playlist.add_channel(channel)

        if not saw_header:
            playlist.warnings.append(
                "missing #EXTM3U header (will be added back on write)"
            )

        return playlist

    def _parse_extinf(self, match: re.Match) -> dict:
        attrs: dict[str, str] = {}
        for attr_match in _ATTR_RE.finditer(match.group("attrs") or ""):
            key = attr_match.group(1).lower()
            value = attr_match.group(2) if attr_match.group(2) is not None else attr_match.group(3)
            attrs[key] = html.unescape(value)
        return {
            "duration": float(match.group("duration")),
            "attrs": attrs,
            "name": html.unescape(match.group("name").strip()),
        }

    def _build_channel(
        self,
        extinf: dict,
        url_line: str,
        category: str | None,
        line_no: int,
        warnings: list[str],
        vlc_opts: dict[str, str] | None = None,
    ) -> Channel | None:
        attrs: dict[str, str] = extinf["attrs"]
        try:
            url = StreamUrl.parse(html.unescape(url_line))
        except InvalidStreamUrlError as exc:
            warnings.append(f"line {line_no}: invalid stream URL, entry skipped: {exc}")
            return None

        name = extinf["name"] or attrs.get("tvg-name") or "Unknown channel"
        tvg_id = TvgId.parse(attrs.get("tvg-id"))
        group_title = GroupTitle.parse(attrs.get("group-title"))
        extra_attrs = {k: v for k, v in attrs.items() if k not in _KNOWN_ATTRS}

        return Channel(
            name=name,
            url=url,
            tvg_id=tvg_id,
            tvg_name=attrs.get("tvg-name"),
            logo_url=attrs.get("tvg-logo"),
            group_title=group_title,
            duration=extinf["duration"],
            source_category=category,
            extra_attrs=extra_attrs,
            vlc_opts=dict(vlc_opts) if vlc_opts else {},
        )

    def serialize(self, playlist: Playlist) -> str:
        lines = ["#EXTM3U"]
        for channel in playlist:
            attr_parts: list[str] = []
            if channel.tvg_id.is_present:
                attr_parts.append(f'tvg-id="{channel.tvg_id}"')
            if channel.tvg_name:
                attr_parts.append(f'tvg-name="{channel.tvg_name}"')
            if channel.logo_url:
                attr_parts.append(f'tvg-logo="{channel.logo_url}"')
            attr_parts.append(f'group-title="{channel.group_title}"')
            for key, value in channel.extra_attrs.items():
                attr_parts.append(f'{key}="{value}"')

            attrs_str = (" " + " ".join(attr_parts)) if attr_parts else ""
            duration = _format_duration(channel.duration)
            lines.append(f"#EXTINF:{duration}{attrs_str},{channel.name}")
            for key, value in channel.vlc_opts.items():
                lines.append(f"#EXTVLCOPT:{key}={value}")
            lines.append(str(channel.url))

        return "\n".join(lines) + "\n"


def _format_duration(duration: float) -> str:
    if duration == int(duration):
        return str(int(duration))
    return str(duration)
