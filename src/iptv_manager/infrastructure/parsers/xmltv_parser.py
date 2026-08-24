"""XMLTV parser.

Extracts <channel> definitions from an XMLTV EPG file using lxml.
Deliberately ignores <programme> elements entirely - Phase 3 only
needs channel-id matching against playlist tvg-ids, not the full
schedule data.

Uses lxml's iterparse for memory efficiency: real-world XMLTV files
(especially ones bundling programme data alongside channels) can be
tens or hundreds of megabytes, and a plain `etree.parse` would load
the whole tree into memory even though we only need <channel>
elements.
"""

from __future__ import annotations

from io import BytesIO

from lxml import etree

from iptv_manager.domain.entities.epg_channel import EPGChannel


class XMLTVParseError(ValueError):
    """Raised when the input isn't parseable as XML at all."""


class XMLTVParser:
    """Concrete implementation of domain.ports.EPGParser."""

    def parse(self, raw_content: str | bytes) -> list[EPGChannel]:
        channels: list[EPGChannel] = []
        if not raw_content or not raw_content.strip():
            return channels
        try:
            # bytes go straight to lxml, which detects the document's
            # real encoding from its XML declaration - this also
            # avoids holding a second full-size copy of a large file
            # in memory just to re-encode text back to bytes.
            raw_bytes = (
                raw_content if isinstance(raw_content, bytes) else raw_content.encode("utf-8")
            )
            stream = BytesIO(raw_bytes)
            context = etree.iterparse(
                stream, events=("end",), tag="channel", recover=True
            )
            for _event, element in context:
                channel = self._element_to_channel(element)
                if channel is not None:
                    channels.append(channel)
                # Free memory for this element and any now-unneeded
                # preceding siblings - required for iterparse to stay
                # O(1) in memory on large files.
                element.clear()
                while element.getprevious() is not None:
                    del element.getparent()[0]
        except etree.XMLSyntaxError as exc:
            raise XMLTVParseError(f"invalid XMLTV document: {exc}") from exc

        return channels

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
