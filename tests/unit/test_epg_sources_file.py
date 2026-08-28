"""Unit tests for infrastructure.sources.epg_sources_file."""

from pathlib import Path

from iptv_manager.infrastructure.sources.epg_sources_file import parse_epg_sources_file


def test_missing_file_returns_empty_list(tmp_path: Path):
    assert parse_epg_sources_file(tmp_path / "does-not-exist.txt") == []


def test_parses_one_url_per_line(tmp_path: Path):
    path = tmp_path / "epg_sources.txt"
    path.write_text(
        "https://a.example.com/epg.xml.gz\nhttps://b.example.com/epg.xml\n", encoding="utf-8"
    )
    assert parse_epg_sources_file(path) == [
        "https://a.example.com/epg.xml.gz",
        "https://b.example.com/epg.xml",
    ]


def test_ignores_blank_lines_and_comments(tmp_path: Path):
    path = tmp_path / "epg_sources.txt"
    path.write_text(
        "\n# a comment\nhttps://a.example.com/epg.xml\n\n  # another comment\n",
        encoding="utf-8",
    )
    assert parse_epg_sources_file(path) == ["https://a.example.com/epg.xml"]


def test_tolerates_a_byte_order_mark(tmp_path: Path):
    path = tmp_path / "epg_sources.txt"
    path.write_bytes("\ufeffhttps://a.example.com/epg.xml\n".encode("utf-8"))
    assert parse_epg_sources_file(path) == ["https://a.example.com/epg.xml"]
