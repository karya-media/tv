"""Use case: assemble every available validation result into one
ValidationReport, ready to be handed to infrastructure/reports
writers. Every input is optional, since not every pipeline run
necessarily includes stream validation, logo validation, or an XMLTV
comparison (e.g. `iptv-manager report --skip-streams`).
"""

from __future__ import annotations

from datetime import UTC, datetime

from iptv_manager.application.dto.validation_report import ValidationReport
from iptv_manager.application.use_cases.compare_with_xmltv import XMLTVComparisonResult
from iptv_manager.application.use_cases.merge_playlists import MergeResult
from iptv_manager.application.use_cases.validate_logos import LogoValidationSummary
from iptv_manager.application.use_cases.validate_streams import StreamValidationSummary


class GenerateReportUseCase:
    def execute(
        self,
        *,
        master_playlist_name: str,
        merge_result: MergeResult | None = None,
        stream_summary: StreamValidationSummary | None = None,
        logo_summary: LogoValidationSummary | None = None,
        epg_comparison: XMLTVComparisonResult | None = None,
    ) -> ValidationReport:
        return ValidationReport(
            generated_at=datetime.now(UTC),
            master_playlist_name=master_playlist_name,
            merge_result=merge_result,
            stream_summary=stream_summary,
            logo_summary=logo_summary,
            epg_comparison=epg_comparison,
        )
