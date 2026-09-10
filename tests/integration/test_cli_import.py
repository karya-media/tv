"""Integration test: `iptv-manager import` saves the source's raw
text byte-for-byte into data/categories/<category>.m3u - group-title
wording, header attributes (url-tvg), attribute formatting/ordering,
and anything else not modeled by this project's domain entities must
all survive untouched. Categorization/ordering/variant-limiting rules
apply later, at merge time, never here.
"""

from pathlib import Path

from typer.testing import CliRunner

import iptv_manager.interfaces.cli.main as cli_main
from iptv_manager.config.settings import Settings, get_settings

runner = CliRunner()


def test_import_saves_the_source_byte_for_byte(tmp_path: Path, monkeypatch):
    get_settings.cache_clear()
    settings = Settings(project_root=tmp_path, github_repository=None)
    settings.ensure_directories()
    monkeypatch.setattr(cli_main, "get_settings", lambda: settings)

    # Deliberately "messy" real-world text this project's own
    # GroupTitle normalization would otherwise rewrite (emoji prefix,
    # extra whitespace) - plus a url-tvg header and unusual attribute
    # ordering/spacing this project doesn't have its own opinion on.
    raw_source = (
        '#EXTM3U url-tvg="https://example.com/epg.xml.gz" x-custom="keep-me"\n'
        '#EXTINF:-1   group-title="📺  Nasional  " tvg-id="X.id",Some Channel\n'
        "http://example.com/stream/x.m3u8\n"
    )
    source_path = tmp_path / "source.m3u"
    source_path.write_text(raw_source, encoding="utf-8")

    result = runner.invoke(cli_main.app, ["import", "mycategory", str(source_path)])

    assert result.exit_code == 0, result.output
    saved_path = settings.categories_path / "mycategory.m3u"
    assert saved_path.read_text(encoding="utf-8") == raw_source
    get_settings.cache_clear()


def test_import_reports_the_parsed_channel_count(tmp_path: Path, monkeypatch):
    get_settings.cache_clear()
    settings = Settings(project_root=tmp_path, github_repository=None)
    settings.ensure_directories()
    monkeypatch.setattr(cli_main, "get_settings", lambda: settings)

    source_path = tmp_path / "source.m3u"
    source_path.write_text(
        "#EXTM3U\n"
        '#EXTINF:-1,A\nhttp://example.com/a.m3u8\n'
        '#EXTINF:-1,B\nhttp://example.com/b.m3u8\n',
        encoding="utf-8",
    )

    result = runner.invoke(cli_main.app, ["import", "mycategory", str(source_path)])

    assert result.exit_code == 0, result.output
    assert "Imported 2 channel(s)" in result.output
    get_settings.cache_clear()
