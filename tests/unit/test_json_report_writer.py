"""Unit tests for infrastructure.reports.json_report_writer."""

import json
from pathlib import Path

from iptv_manager.infrastructure.reports.json_report_writer import JSONReportWriter
from tests.unit.report_test_helpers import build_full_report, build_minimal_report


def test_full_report_produces_all_sections(tmp_path: Path):
    output = tmp_path / "report.json"
    JSONReportWriter().write(build_full_report(), output)
    data = json.loads(output.read_text(encoding="utf-8"))

    assert set(data.keys()) >= {
        "generated_at", "master_playlist_name", "merge", "streams", "logos", "epg"
    }


def test_merge_section_values(tmp_path: Path):
    output = tmp_path / "report.json"
    JSONReportWriter().write(build_full_report(), output)
    data = json.loads(output.read_text(encoding="utf-8"))

    assert data["merge"]["total_channels_before"] == 3
    assert data["merge"]["total_channels_after"] == 2
    assert data["merge"]["duplicate_urls_removed"] == 1
    assert data["merge"]["duplicate_tvg_id_groups"][0]["tvg_id"] == "espn.us"


def test_streams_section_values(tmp_path: Path):
    output = tmp_path / "report.json"
    JSONReportWriter().write(build_full_report(), output)
    data = json.loads(output.read_text(encoding="utf-8"))

    assert data["streams"]["total"] == 2
    assert data["streams"]["online"] == 1
    statuses = {r["status"] for r in data["streams"]["results"]}
    assert statuses == {"online", "offline"}


def test_epg_section_values(tmp_path: Path):
    output = tmp_path / "report.json"
    JSONReportWriter().write(build_full_report(), output)
    data = json.loads(output.read_text(encoding="utf-8"))

    assert data["epg"]["invalid_tvg_id"] == [{"name": "Fox Sports", "tvg_id": "fox.us"}]
    assert data["epg"]["unused_epg_entries"] == ["unused.us"]


def test_minimal_report_omits_absent_sections(tmp_path: Path):
    output = tmp_path / "report.json"
    JSONReportWriter().write(build_minimal_report(), output)
    data = json.loads(output.read_text(encoding="utf-8"))

    assert "merge" in data
    assert "streams" not in data
    assert "logos" not in data
    assert "epg" not in data


def test_output_is_valid_utf8_json(tmp_path: Path):
    output = tmp_path / "report.json"
    JSONReportWriter().write(build_full_report(), output)
    # Must not raise - proves the file is valid JSON with real UTF-8 content.
    json.loads(output.read_text(encoding="utf-8"))
