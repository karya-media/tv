"""Unit tests for infrastructure.reports.csv_report_writer."""

import csv
from pathlib import Path

from iptv_manager.infrastructure.reports.csv_report_writer import CSVReportWriter
from tests.unit.report_test_helpers import build_full_report, build_minimal_report


def _read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_one_row_per_stream_result(tmp_path: Path):
    output = tmp_path / "report.csv"
    CSVReportWriter().write(build_full_report(), output)
    rows = _read_rows(output)
    assert len(rows) == 2
    names = {r["name"] for r in rows}
    assert names == {"ESPN", "Fox Sports"}


def test_logo_status_joined_by_url_not_identity(tmp_path: Path):
    output = tmp_path / "report.csv"
    CSVReportWriter().write(build_full_report(), output)
    rows = {r["name"]: r for r in _read_rows(output)}
    assert rows["ESPN"]["logo_status"] == "reachable"
    assert rows["Fox Sports"]["logo_status"] == "missing"


def test_stream_status_and_http_status_present(tmp_path: Path):
    output = tmp_path / "report.csv"
    CSVReportWriter().write(build_full_report(), output)
    rows = {r["name"]: r for r in _read_rows(output)}
    assert rows["ESPN"]["stream_status"] == "online"
    assert rows["ESPN"]["http_status"] == "200"
    assert rows["Fox Sports"]["stream_status"] == "offline"


def test_falls_back_to_merge_result_when_no_stream_summary(tmp_path: Path):
    output = tmp_path / "report.csv"
    CSVReportWriter().write(build_minimal_report(), output)
    rows = _read_rows(output)
    assert len(rows) == 1
    assert rows[0]["name"] == "CNN"
    assert rows[0]["stream_status"] == ""


def test_header_row_matches_expected_fieldnames(tmp_path: Path):
    output = tmp_path / "report.csv"
    CSVReportWriter().write(build_full_report(), output)
    with output.open(encoding="utf-8") as f:
        header = f.readline().strip()
    assert header == (
        "name,group_title,tvg_id,url,stream_status,http_status,response_time_ms,logo_status"
    )
