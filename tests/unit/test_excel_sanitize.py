"""Unit tests for infrastructure.reports.excel_sanitize."""

from iptv_manager.infrastructure.reports.excel_sanitize import sanitize_for_excel


def test_strips_xml_illegal_control_characters():
    assert sanitize_for_excel("Hello\x00World") == "HelloWorld"
    assert sanitize_for_excel("A\x0bB\x0cC") == "ABC"
    assert sanitize_for_excel("X\x1fY") == "XY"


def test_leaves_normal_text_unchanged():
    assert sanitize_for_excel("RCTI HD (720p)") == "RCTI HD (720p)"
    assert sanitize_for_excel("Berita 📺 Indonesia") == "Berita 📺 Indonesia"


def test_tab_newline_and_carriage_return_are_preserved():
    # These are legal in XML 1.0 and openpyxl handles them fine -
    # only the narrower "illegal" set should be stripped.
    assert sanitize_for_excel("A\tB\nC\rD") == "A\tB\nC\rD"


def test_non_string_values_pass_through_unchanged():
    assert sanitize_for_excel(42) == 42
    assert sanitize_for_excel(None) is None
    assert sanitize_for_excel(3.14) == 3.14


def test_empty_string_stays_empty():
    assert sanitize_for_excel("") == ""
