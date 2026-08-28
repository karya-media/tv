"""XMLTV parser.

Extracts <channel> definitions from an XMLTV EPG file using lxml. The
default parse() method deliberately ignores <programme> elements
entirely - tvg-id matching (the original, still most common use of
this parser) only needs channel identity, not the full schedule data.

parse_channels_and_programmes() additionally extracts <programme>
elements, but only for a caller-supplied set of wanted channel ids
(e.g. every tvg-id actually present in master.m3u) - see
MergeEPGSourcesUseCase for why: a full multi-source aggregated EPG's
programme data for *every* channel in the world, across many days, is
what caused a real out-of-memory failure earlier in this project (see
git history around "fix: fetch and parse EPG XML as bytes"). Filtering
during the streaming parse itself, rather than parsing everything and
filtering after, is what keeps memory proportional to "channels we
actually care about" instead of "size of the source file".

Uses lxml's iterparse for memory efficiency: real-world XMLTV files
(especially ones bundling programme data alongside channels) can be
tens or hundreds of megabytes, and a plain `etree.parse` would load
the whole tree into memory even though we only need specific elements.
"""

from __future__ import annotations

from io import BytesIO

from lxml import etree

from iptv_manager.domain.entities.epg_channel import EPGChannel
from iptv_manager.domain.entities.epg_programme import EPGProgramme


class XMLTVParseError(ValueError):
    """Raised when the input isn't parseable as XML at all."""


class XMLTVParser:
    """Concrete implementation of domain.ports.EPGParser."""

    def parse(self, raw_content: str | bytes) -> list[EPGChannel]:
        channels, _programmes = self._parse(raw_content, wanted_channel_ids=None)
        return channels

    def parse_channels_and_programmes(
        self, raw_content: str | bytes, wanted_channel_ids: set[str]
    ) -> tuple[list[EPGChannel], list[EPGProgramme]]:
        """Like parse(), but also returns every <programme> whose
        channel="..." attribute is in wanted_channel_ids (matched
        case-insensitively, since tvg-id casing varies across
        sources). Programmes for any other channel are discarded
        during the streaming parse itself and never held in memory."""
        return self._parse(raw_content, wanted_channel_ids=wanted_channel_ids)

    def _parse(
        self, raw_content: str | bytes, wanted_channel_ids: set[str] | None
    ) -> tuple[list[EPGChannel], list[EPGProgramme]]:
        channels: list[EPGChannel] = []
        programmes: list[EPGProgramme] = []
        if not raw_content or not raw_content.strip():
            return channels, programmes

        wanted_lower = (
            {c.strip().casefold() for c in wanted_channel_ids}
            if wanted_channel_ids is not None
            else None
        )
        tags = ("channel", "programme") if wanted_lower is not None else ("channel",)

        try:
            # bytes go straight to lxml, which detects the document's
            # real encoding from its XML declaration - this also
            # avoids holding a second full-size copy of a large file
            # in memory just to re-encode text back to bytes.
            raw_bytes = (
                raw_content if isinstance(raw_content, bytes) else raw_content.encode("utf-8")
            )
            stream = BytesIO(raw_bytes)
            context = etree.iterparse(stream, events=("end",), tag=tags, recover=True)
            for _event, element in context:
                if element.tag == "channel":
                    channel = self._element_to_channel(element)
                    if channel is not None and (
                        wanted_lower is None or channel.id.casefold() in wanted_lower
                    ):
                        channels.append(channel)
                elif element.tag == "programme" and wanted_lower is not None:
                    programme = self._element_to_programme(element, wanted_lower)
                    if programme is not None:
                        programmes.append(programme)
                # Free memory for this element and any now-unneeded
                # preceding siblings - required for iterparse to stay
                # O(1) in memory on large files.
                element.clear()
                while element.getprevious() is not None:
                    del element.getparent()[0]
        except etree.XMLSyntaxError as exc:
            raise XMLTVParseError(f"invalid XMLTV document: {exc}") from exc

        return channels, programmes

    def _element_to_channel(self, element: etree._Element) -> EPGChannel | None:
        channel_id = element.get("id")
        if not channel_id or not channel_id.strip():
            return None

        display_names = tuple(
            (node.text or "").strip()
            for node in element.findall("display-name")
            if node.text and node.text.strip()
        )
        icon_node = element.find("icon")
        icon_url = icon_node.get("src") if icon_node is not None else None

        return EPGChannel(id=channel_id.strip(), display_names=display_names, icon_url=icon_url)

    def _element_to_programme(
        self, element: etree._Element, wanted_lower: set[str]
    ) -> EPGProgramme | None:
        channel_id = element.get("channel")
        if not channel_id or channel_id.strip().casefold() not in wanted_lower:
            return None
        start = element.get("start")
        if not start:
            return None
        title_node = element.find("title")
        title = (title_node.text or "").strip() if title_node is not None else ""
        if not title:
            return None
        desc_node = element.find("desc")
        category_node = element.find("category")

        return EPGProgramme(
            channel_id=channel_id.strip(),
            start=start.strip(),
            stop=(element.get("stop") or "").strip() or None,
            title=title,
            description=(
                (desc_node.text or "").strip() or None if desc_node is not None else None
            ),
            category=(
                (category_node.text or "").strip() or None
                if category_node is not None
                else None
            ),
        )
