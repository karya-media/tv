"""Unit tests for infrastructure.serializers.xmltv_writer."""

from iptv_manager.domain.entities.epg_channel import EPGChannel
from iptv_manager.domain.entities.epg_programme import EPGProgramme
from iptv_manager.infrastructure.parsers.xmltv_parser import XMLTVParser
from iptv_manager.infrastructure.serializers.xmltv_writer import write_xmltv


def test_output_starts_with_xml_declaration():
    output = write_xmltv([], [])
    assert output.startswith(b"<?xml version='1.0' encoding='UTF-8'?>") or output.startswith(
        b'<?xml version="1.0" encoding="UTF-8"?>'
    )


def test_output_is_valid_bytes_not_str():
    output = write_xmltv([], [])
    assert isinstance(output, bytes)


def test_round_trips_through_the_parser():
    channels = [
        EPGChannel(
            id="rcti.id",
            display_names=("RCTI", "RCTI HD"),
            icon_url="https://example.com/rcti.png",
        ),
    ]
    programmes = [
        EPGProgramme(
            channel_id="rcti.id",
            start="20260827100000 +0700",
            stop="20260827110000 +0700",
            title="Berita Pagi",
            description="Program berita pagi RCTI.",
            category="News",
        ),
    ]
    output = write_xmltv(channels, programmes)

    parsed_channels = XMLTVParser().parse(output)
    assert len(parsed_channels) == 1
    assert parsed_channels[0].id == "rcti.id"
    assert parsed_channels[0].display_names == ("RCTI", "RCTI HD")
    assert parsed_channels[0].icon_url == "https://example.com/rcti.png"

    _channels, parsed_programmes = XMLTVParser().parse_channels_and_programmes(
        output, wanted_channel_ids={"rcti.id"}
    )
    assert len(parsed_programmes) == 1
    p = parsed_programmes[0]
    assert p.title == "Berita Pagi"
    assert p.description == "Program berita pagi RCTI."
    assert p.category == "News"
    assert p.start == "20260827100000 +0700"
    assert p.stop == "20260827110000 +0700"


def test_special_characters_are_escaped_safely():
    channels = [EPGChannel(id="x", display_names=('Rock & Roll "TV"',))]
    output = write_xmltv(channels, [])
    # Must not corrupt the XML structure - re-parsing must recover the
    # exact original text.
    parsed = XMLTVParser().parse(output)
    assert parsed[0].display_names == ('Rock & Roll "TV"',)


def test_programme_without_stop_omits_the_stop_attribute():
    programmes = [
        EPGProgramme(channel_id="x", start="20260827100000 +0700", stop=None, title="Show"),
    ]
    output = write_xmltv([], programmes)
    assert b'stop="' not in output


def test_programme_without_description_or_category_omits_those_tags():
    programmes = [
        EPGProgramme(
            channel_id="x", start="20260827100000 +0700", stop=None, title="Show"
        ),
    ]
    output = write_xmltv([], programmes)
    assert b"<desc>" not in output
    assert b"<category>" not in output


def test_empty_input_still_produces_a_valid_tv_root_element():
    output = write_xmltv([], [])
    parsed = XMLTVParser().parse(output)
    assert parsed == []
