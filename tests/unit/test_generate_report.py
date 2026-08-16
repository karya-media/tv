"""Unit tests for application.use_cases.generate_report."""

from datetime import datetime

from iptv_manager.application.use_cases.generate_report import GenerateReportUseCase
from tests.unit.report_test_helpers import build_full_report, build_minimal_report


def test_report_has_generated_at_timestamp():
    result = GenerateReportUseCase().execute(master_playlist_name="master")
    assert isinstance(result.generated_at, datetime)
    assert result.generated_at.tzinfo is not None


def test_report_carries_through_all_provided_results():
    full = build_full_report()
    result = GenerateReportUseCase().execute(
        master_playlist_name="master",
        merge_result=full.merge_result,
        stream_summary=full.stream_summary,
        logo_summary=full.logo_summary,
        epg_comparison=full.epg_comparison,
    )
    assert result.merge_result is full.merge_result
    assert result.stream_summary is full.stream_summary
    assert result.logo_summary is full.logo_summary
    assert result.epg_comparison is full.epg_comparison


def test_report_allows_all_optional_fields_to_be_none():
    result = GenerateReportUseCase().execute(master_playlist_name="master")
    assert result.merge_result is None
    assert result.stream_summary is None
    assert result.logo_summary is None
    assert result.epg_comparison is None


def test_helper_minimal_report_has_only_merge_result():
    report = build_minimal_report()
    assert report.merge_result is not None
    assert report.stream_summary is None
    assert report.logo_summary is None
    assert report.epg_comparison is None
