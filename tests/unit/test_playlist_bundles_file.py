"""Unit tests for infrastructure.sources.playlist_bundles_file."""

import pytest

from iptv_manager.infrastructure.sources.playlist_bundles_file import (
    PlaylistBundle,
    PlaylistBundlesFileError,
    parse_playlist_bundles_file,
)


def test_missing_file_returns_empty_dict(tmp_path):
    assert parse_playlist_bundles_file(tmp_path / "does-not-exist.txt") == {}


def test_parses_a_plain_stem_bundle(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("master=sports,news\n", encoding="utf-8")
    result = parse_playlist_bundles_file(path)
    assert result == {"master": PlaylistBundle(stems=["sports", "news"], group_prefixes=[])}


def test_parses_a_group_prefix_bundle(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("indonesia=group:Indonesia\n", encoding="utf-8")
    result = parse_playlist_bundles_file(path)
    assert result == {
        "indonesia": PlaylistBundle(stems=[], group_prefixes=["Indonesia"])
    }


def test_mixes_stems_and_group_prefixes_in_one_bundle(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("mixed=sports,group:Indonesia,group:Germany\n", encoding="utf-8")
    result = parse_playlist_bundles_file(path)
    assert result == {
        "mixed": PlaylistBundle(stems=["sports"], group_prefixes=["Indonesia", "Germany"])
    }


def test_group_marker_is_case_insensitive(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("indonesia=GROUP:Indonesia\n", encoding="utf-8")
    result = parse_playlist_bundles_file(path)
    assert result["indonesia"].group_prefixes == ["Indonesia"]


def test_ignores_blank_lines_and_comments(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("\n# comment\nmaster=sports\n\n", encoding="utf-8")
    result = parse_playlist_bundles_file(path)
    assert result == {"master": PlaylistBundle(stems=["sports"], group_prefixes=[])}


def test_whitespace_around_entries_is_ignored(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("master = sports , group:Indonesia \n", encoding="utf-8")
    result = parse_playlist_bundles_file(path)
    assert result["master"] == PlaylistBundle(stems=["sports"], group_prefixes=["Indonesia"])


def test_missing_equals_sign_raises(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("this is not valid\n", encoding="utf-8")
    with pytest.raises(PlaylistBundlesFileError):
        parse_playlist_bundles_file(path)


def test_empty_bundle_name_raises(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("=sports\n", encoding="utf-8")
    with pytest.raises(PlaylistBundlesFileError):
        parse_playlist_bundles_file(path)


def test_path_traversal_in_bundle_name_raises(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("../evil=sports\n", encoding="utf-8")
    with pytest.raises(PlaylistBundlesFileError):
        parse_playlist_bundles_file(path)


def test_bundle_with_no_entries_raises(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("master=\n", encoding="utf-8")
    with pytest.raises(PlaylistBundlesFileError):
        parse_playlist_bundles_file(path)


def test_empty_group_prefix_raises(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("master=group:\n", encoding="utf-8")
    with pytest.raises(PlaylistBundlesFileError):
        parse_playlist_bundles_file(path)


def test_duplicate_bundle_name_raises(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("master=sports\nmaster=news\n", encoding="utf-8")
    with pytest.raises(PlaylistBundlesFileError):
        parse_playlist_bundles_file(path)


def test_tolerates_a_byte_order_mark(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_bytes("\ufeffmaster=sports\n".encode("utf-8"))
    result = parse_playlist_bundles_file(path)
    assert result == {"master": PlaylistBundle(stems=["sports"], group_prefixes=[])}


def test_parses_the_all_stems_wildcard(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("master=*\n", encoding="utf-8")
    result = parse_playlist_bundles_file(path)
    assert result == {"master": PlaylistBundle(all_stems=True)}


def test_wildcard_combined_with_a_stem_raises(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("master=*,sports\n", encoding="utf-8")
    with pytest.raises(PlaylistBundlesFileError):
        parse_playlist_bundles_file(path)


def test_wildcard_combined_with_a_group_prefix_raises(tmp_path):
    path = tmp_path / "playlists.txt"
    path.write_text("master=*,group:Indonesia\n", encoding="utf-8")
    with pytest.raises(PlaylistBundlesFileError):
        parse_playlist_bundles_file(path)
