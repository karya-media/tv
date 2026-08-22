"""Use case: the complete validation pipeline - merge category
playlists, validate streams, validate logos, optionally compare
against an XMLTV EPG, and assemble a ValidationReport.

This is the single orchestration point shared by the CLI `report`
command, the REST API's trigger endpoint, and the background
scheduler, so a manually triggered run and a scheduled run behave
identically instead of each re-implementing the pipeline. File I/O
(writing master.m3u, writing report files) deliberately stays out of
this use case - that's an interfaces-layer concern, since different
callers may want different side effects (the CLI always writes to
disk; a future test runner might not).
"""

from __future__ import annotations

from dataclasses import dataclass

from iptv_manager.application.dto.validation_report import ValidationReport
from iptv_manager.application.use_cases.backfill_tvg_id import BackfillTvgIdFromExactNameUseCase
from iptv_manager.application.use_cases.categorize_by_country import CategorizeByCountryUseCase
from iptv_manager.application.use_cases.compare_with_xmltv import CompareWithXMLTVUseCase
from iptv_manager.application.use_cases.generate_report import GenerateReportUseCase
from iptv_manager.application.use_cases.merge_playlists import MergePlaylistsUseCase
from iptv_manager.application.use_cases.validate_logos import ValidateLogosUseCase
from iptv_manager.application.use_cases.validate_streams import ValidateStreamsUseCase
from iptv_manager.domain.entities.epg_channel import EPGChannel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.ports.logo_validator import LogoValidator
from iptv_manager.domain.ports.stream_validator import StreamValidator


@dataclass(slots=True)
class RunFullPipelineUseCase:
    stream_validator: StreamValidator | None = None
    logo_validator: LogoValidator | None = None

    async def execute(
        self,
        category_playlists: list[Playlist],
        *,
        epg_channels: list[EPGChannel] | None = None,
    ) -> ValidationReport:
        merge_result = MergePlaylistsUseCase().execute(category_playlists, master_name="master")
        merge_result.master = BackfillTvgIdFromExactNameUseCase().execute(merge_result.master)
        merge_result.master = CategorizeByCountryUseCase().execute(merge_result.master)

        stream_summary = None
        if self.stream_validator is not None:
            stream_summary = await ValidateStreamsUseCase(
                validator=self.stream_validator
            ).execute(merge_result.master)

        logo_summary = None
        if self.logo_validator is not None:
            logo_summary = await ValidateLogosUseCase(validator=self.logo_validator).execute(
                merge_result.master
            )

        epg_comparison = None
        if epg_channels is not None:
            epg_comparison = CompareWithXMLTVUseCase().execute(merge_result.master, epg_channels)

        return GenerateReportUseCase().execute(
            master_playlist_name="master",
            merge_result=merge_result,
            stream_summary=stream_summary,
            logo_summary=logo_summary,
            epg_comparison=epg_comparison,
        )
