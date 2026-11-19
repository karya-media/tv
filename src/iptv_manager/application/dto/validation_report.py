from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from iptv_manager.application.use_cases.compare_with_xmltv import XMLTVComparisonResult
from iptv_manager.application.use_cases.merge_playlists import MergeResult
from iptv_manager.application.use_cases.validate_logos import LogoValidationSummary
from iptv_manager.application.use_cases.validate_streams import StreamValidationSummary


@dataclass(slots=True)
class ValidationReport:
    generated_at: datetime
    master_playlist_name: str
    merge_result: MergeResult | None = None
    stream_summary: StreamValidationSummary | None = None
    logo_summary: LogoValidationSummary | None = None
    epg_comparison: XMLTVComparisonResult | None = None
