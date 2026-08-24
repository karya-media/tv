"""Unit tests for infrastructure.parsers.xmltv_parser.XMLTVParser."""

from pathlib import Path

import pytest

from iptv_manager.infrastructure.parsers.xmltv_parser import XMLTVParser

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def parser() -> XMLTVParser:
    return XMLTVParser()


def test_parses_all_channels(parser: XMLTVParser):
    raw = FIXTURES.joinpath("epg.xml").read_text(encoding="utf-8")
    channels = parser.parse(raw)
    ids = {c.id for c in channels}
    assert ids == {"espn.us", "cnn.us", "unused.channel.us"}


def test_display_names_captured_in_order(parser: XMLTVParser):
    raw = FIXTURES.joinpath("epg.xml").read_text(encoding="utf-8")
    channels = {c.id: c for c in parser.parse(raw)}
    assert channels["espn.us"].display_names == ("ESPN", "ESPN HD")
    assert channels["espn.us"].primary_display_name == "ESPN"


def test_icon_url_captured(parser: XMLTVParser):
    raw = FIXTURES.joinpath("epg.xml").read_text(encoding="utf-8")
    channels = {c.id: c for c in parser.parse(raw)}
    assert channels["espn.us"].icon_url == "https://epg.example.com/logos/espn.png"


def test_channel_without_icon_has_none(parser: XMLTVParser):
    raw = FIXTURES.joinpath("epg.xml").read_text(encoding="utf-8")
    channels = {c.id: c for c in parser.parse(raw)}
    assert channels["cnn.us"].icon_url is None


def test_channel_missing_id_is_skipped(parser: XMLTVParser):
    raw = '<tv><channel><display-name>No ID</display-name></channel></tv>'
    channels = parser.parse(raw)
    assert channels == []


def test_programme_elements_are_ignored(parser: XMLTVParser):
    raw = FIXTURES.joinpath("epg.xml").read_text(encoding="utf-8")
    channels = parser.parse(raw)
    # Only 3 <channel> elements exist despite a <programme> also being present.
    assert len(channels) == 3


def test_unclosed_tag_is_repaired_rather_than_rejected(parser: XMLTVParser):
    # lxml's recover mode auto-closes malformed tags instead of failing
    # outright - consistent with this project's "repair, don't abort"
    # philosophy for slightly broken real-world files.
    channels = parser.parse("<tv><channel id='x'>not closed")
    assert [c.id for c in channels] == ["x"]


def test_completely_non_xml_input_yields_empty_list_without_raising(parser: XMLTVParser):
    channels = parser.parse("this is not xml at all !!! @#$%")
    assert channels == []


def test_empty_string_yields_empty_list(parser: XMLTVParser):
    assert parser.parse("") == []


def test_parses_raw_bytes_directly_without_a_str_round_trip(parser: XMLTVParser):
    raw_bytes = FIXTURES.joinpath("epg.xml").read_bytes()
    channels = parser.parse(raw_bytes)
    ids = {c.id for c in channels}
    assert ids == {"espn.us", "cnn.us", "unused.channel.us"}


def test_empty_bytes_yields_empty_list(parser: XMLTVParser):
    assert parser.parse(b"") == []
