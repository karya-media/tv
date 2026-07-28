"""Shared pipeline execution + persistence logic.

Used by both the REST API's trigger endpoint (via BackgroundTasks) and
the internal APScheduler job, so a manually triggered run and a
scheduled run behave identically and both show up in the same history
table (domain.entities.pipeline_run.PipelineRun, persisted through
PipelineRunRepository).
"""

from __future__ import annotations

from datetime import UTC, datetime

from iptv_manager.application.use_cases.run_full_pipeline import RunFullPipelineUseCase
from iptv_manager.config.settings import PublishTarget, Settings
from iptv_manager.domain.entities.pipeline_run import PipelineRun, PipelineRunStatus
from iptv_manager.domain.ports.pipeline_run_repository import PipelineRunRepository
from iptv_manager.infrastructure.parsers.m3u_parser import M3UParser
from iptv_manager.infrastructure.reports.csv_report_writer import CSVReportWriter
from iptv_manager.infrastructure.reports.excel_report_writer import ExcelReportWriter
from iptv_manager.infrastructure.reports.html_report_writer import HTMLReportWriter
from iptv_manager.infrastructure.reports.json_report_writer import JSONReportWriter
from iptv_manager.infrastructure.sources.local_file_source import LocalFilePlaylistSource
from iptv_manager.infrastructure.validators.http_stream_validator import HttpStreamValidator
from iptv_manager.infrastructure.validators.logo_validator import LogoImageValidator


async def create_running_run(run_repository: PipelineRunRepository) -> PipelineRun:
    """Insert a placeholder RUNNING record immediately, so a caller
    (the API endpoint) can return a run_id right away without waiting
    for the pipeline to finish."""
    return await run_repository.save(
        PipelineRun(
            id=None, started_at=datetime.now(UTC), status=PipelineRunStatus.RUNNING
        )
    )


async def execute_and_persist(
    run: PipelineRun, *, settings: Settings, run_repository: PipelineRunRepository
) -> PipelineRun:
    """Run the full pipeline for an already-created (RUNNING) run
    record, then update that same record with the outcome. Never
    raises - failures are recorded on the run itself so the dashboard
    can show them, rather than crashing a background task silently.
    """
    settings.ensure_directories()
    parser = M3UParser()

    category_files = sorted(
        set(settings.categories_path.glob("*.m3u")) | set(settings.categories_path.glob("*.m3u8"))
    )
    if not category_files:
        run.status = PipelineRunStatus.FAILED
        run.finished_at = datetime.now(UTC)
        run.error_message = f"no category playlists found in {settings.categories_path}"
        return await run_repository.update(run)

    try:
        playlists = []
        for path in category_files:
            raw_text = await LocalFilePlaylistSource(path).fetch()
            playlists.append(parser.parse(raw_text, name=path.stem, category=path.stem))

        stream_validator = HttpStreamValidator(
            timeout_seconds=settings.validation_timeout_seconds,
            max_concurrency=settings.validation_max_concurrency,
            user_agent=settings.user_agent,
            retries=settings.validation_retries,
        )
        logo_validator = LogoImageValidator(
            timeout_seconds=settings.validation_timeout_seconds,
            max_concurrency=settings.validation_max_concurrency,
            user_agent=settings.user_agent,
        )

        report = await RunFullPipelineUseCase(
            stream_validator=stream_validator, logo_validator=logo_validator
        ).execute(playlists)

        master_text = parser.serialize(report.merge_result.master)
        settings.master_playlist_path.write_text(master_text, encoding="utf-8")
        if settings.publish_target in (PublishTarget.PAGES_ONLY, PublishTarget.BOTH):
            settings.docs_master_playlist_path.write_text(master_text, encoding="utf-8")

        reports_dir = settings.project_root / settings.reports_dir
        reports_dir.mkdir(parents=True, exist_ok=True)
        HTMLReportWriter().write(report, reports_dir / "report.html")
        JSONReportWriter().write(report, reports_dir / "report.json")
        CSVReportWriter().write(report, reports_dir / "report.csv")
        ExcelReportWriter().write(report, reports_dir / "report.xlsx")

        run.status = PipelineRunStatus.SUCCESS
        run.channels_before = report.merge_result.total_channels_before
        run.channels_after = report.merge_result.total_channels_after
        run.duplicate_urls_removed = report.merge_result.removed_duplicate_url_count
        if report.stream_summary is not None:
            run.online_count = report.stream_summary.online_count
            run.offline_count = report.stream_summary.offline_count
        if report.logo_summary is not None:
            run.logos_reachable = report.logo_summary.reachable_count
            run.logos_missing = report.logo_summary.missing_count
        if report.epg_comparison is not None:
            run.epg_invalid_tvg_id = len(report.epg_comparison.invalid_tvg_id)
    except Exception as exc:  # noqa: BLE001 - persisted for the dashboard, never re-raised
        run.status = PipelineRunStatus.FAILED
        run.error_message = str(exc)

    run.finished_at = datetime.now(UTC)
    return await run_repository.update(run)


async def scheduled_pipeline_job(
    *, settings: Settings, run_repository: PipelineRunRepository
) -> None:
    """Entry point registered with APScheduler."""
    run = await create_running_run(run_repository)
    await execute_and_persist(run, settings=settings, run_repository=run_repository)
