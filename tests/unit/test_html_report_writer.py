"""Unit tests for infrastructure.reports.html_report_writer."""

from pathlib import Path

from iptv_manager.infrastructure.reports.html_report_writer import HTMLReportWriter
from tests.unit.report_test_helpers import build_full_report, build_minimal_report


def test_produces_valid_looking_html(tmp_path: Path):
    output = tmp_path / "report.html"
    HTMLReportWriter().write(build_full_report(), output)
    html = output.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html


def test_channel_names_appear_in_output(tmp_path: Path):
    output = tmp_path / "report.html"
    HTMLReportWriter().write(build_full_report(), output)
    html = output.read_text(encoding="utf-8")
    assert "ESPN" in html
    assert "Fox Sports" in html


def test_sections_only_render_when_data_present(tmp_path: Path):
    output = tmp_path / "report.html"
    HTMLReportWriter().write(build_minimal_report(), output)
    html = output.read_text(encoding="utf-8")
    assert "Merge Summary" in html
    assert "Stream Validation" not in html
    assert "Logo Validation" not in html
    assert "XMLTV / EPG Comparison" not in html


def test_autoescape_prevents_html_injection_from_channel_names(tmp_path: Path):
    from datetime import datetime, timezone

    from iptv_manager.application.dto.validation_report import ValidationReport
    from iptv_manager.application.use_cases.merge_playlists import DuplicateUrlGroup, MergeResult
    from iptv_manager.domain.entities.playlist import Playlist
    from tests.unit.report_test_helpers import make_channel

    safe = make_channel("Safe Channel", "http://x.com/a.m3u8")
    malicious = make_channel("<script>alert(1)</script>", "http://x.com/a.m3u8")
    master = Playlist(name="master", channels=[safe])
    merge_result = MergeResult(
        master=master,
        total_channels_before=2,
        total_channels_after=1,
        duplicate_urls=[
            DuplicateUrlGroup(key="http://x.com/a.m3u8", kept=safe, removed=[malicious])
        ],
    )
    report = ValidationReport(
        generated_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
        master_playlist_name="master",
        merge_result=merge_result,
    )

    output = tmp_path / "report.html"
    HTMLReportWriter().write(report, output)
    html = output.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
