"""ValidationReport DTO.

Aggregates the results of every earlier use case (merge, stream
validation, logo validation, XMLTV comparison) into one object that
Phase 4's report writers (infrastructure/reports/) render into
HTML/JSON/CSV/Excel.

Deliberately placed in the application layer rather than domain: this
is a shape describing *use case outputs*, not a business concept in
its own right, and its fields are typed against other use cases'
result dataclasses (MergeResult, StreamValidationSummary, ...) - typing
it here avoids creating a domain -> application dependency that would
exist if it lived in domain/entities instead.
"""

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
