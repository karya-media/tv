"""XMLTV writer.

Serializes EPGChannel + EPGProgramme entities back to a valid XMLTV
document - the counterpart to XMLTVParser, used to write out this
project's own merged EPG file (see MergeEPGSourcesUseCase).

Builds the document with lxml's Element API rather than manual string
formatting, so text content is properly XML-escaped automatically
(titles/descriptions from real-world EPG sources routinely contain
"&", "<", quotes, etc.) instead of risking malformed or unsafe output.
"""

from __future__ import annotations

from lxml import etree

from iptv_manager.domain.entities.epg_channel import EPGChannel
from iptv_manager.domain.entities.epg_programme import EPGProgramme


def write_xmltv(
    channels: list[EPGChannel],
    programmes: list[EPGProgramme],
    generator_name: str = "karya-media/tv",
) -> bytes:
    """Returns a complete XMLTV document as UTF-8 bytes, including the
    <?xml ...?> declaration."""
    root = etree.Element("tv", attrib={"generator-info-name": generator_name})

    for channel in channels:
        channel_el = etree.SubElement(root, "channel", attrib={"id": channel.id})
        for display_name in channel.display_names:
            name_el = etree.SubElement(channel_el, "display-name")
            name_el.text = display_name
        if channel.icon_url:
            etree.SubElement(channel_el, "icon", attrib={"src": channel.icon_url})

    for programme in programmes:
        attrib = {"start": programme.start, "channel": programme.channel_id}
        if programme.stop:
            attrib["stop"] = programme.stop
        programme_el = etree.SubElement(root, "programme", attrib=attrib)
        title_el = etree.SubElement(programme_el, "title")
        title_el.text = programme.title
        if programme.description:
            desc_el = etree.SubElement(programme_el, "desc")
            desc_el.text = programme.description
        if programme.category:
            category_el = etree.SubElement(programme_el, "category")
            category_el.text = programme.category

    return etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", pretty_print=True
    )
