"""CLI entrypoints, primarily invoked by GitHub Actions workflows
but equally usable by hand.

Commands:
    iptv-manager import CATEGORY SOURCE   - import one category playlist
    iptv-manager sync-sources              - re-import every category listed in data/sources.txt
    iptv-manager merge                    - merge all categories into master.m3u
    iptv-manager validate                 - validate every stream in master.m3u
    iptv-manager check-logos              - validate every channel's logo image
    iptv-manager check-epg XMLTV_SOURCE   - compare master.m3u tvg-ids against an XMLTV EPG
    iptv-manager report                   - full pipeline (merge+validate+logos[+epg]) -> reports/
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

import typer

from iptv_manager.application.dto.validation_report import ValidationReport
from iptv_manager.application.use_cases.apply_channel_order import ApplyChannelOrderUseCase
from iptv_manager.application.use_cases.backfill_tvg_id import BackfillTvgIdFromExactNameUseCase
from iptv_manager.application.use_cases.categorize_by_country import CategorizeByCountryUseCase
from iptv_manager.application.use_cases.compare_with_xmltv import CompareWithXMLTVUseCase
from iptv_manager.application.use_cases.generate_report import GenerateReportUseCase
from iptv_manager.application.use_cases.import_playlist import ImportPlaylistUseCase
from iptv_manager.application.use_cases.match_tvg_id_from_epg import MatchTvgIdFromEpgUseCase
from iptv_manager.application.use_cases.merge_playlists import MergePlaylistsUseCase, MergeResult
from iptv_manager.application.use_cases.sync_sources import SyncSourcesUseCase
from iptv_manager.application.use_cases.validate_logos import (
    LogoValidationSummary,
    ValidateLogosUseCase,
)
from iptv_manager.application.use_cases.validate_streams import (
    StreamValidationSummary,
    ValidateStreamsUseCase,
)
from iptv_manager.config.settings import PublishTarget, Settings, get_settings
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.entities.stream_validation_result import StreamStatus
from iptv_manager.infrastructure.parsers.m3u_parser import M3UParser
from iptv_manager.infrastructure.parsers.xmltv_parser import XMLTVParser
from iptv_manager.infrastructure.reports.csv_report_writer import CSVReportWriter
from iptv_manager.infrastructure.reports.excel_report_writer import ExcelReportWriter
from iptv_manager.infrastructure.reports.html_report_writer import HTMLReportWriter
from iptv_manager.infrastructure.reports.json_report_writer import JSONReportWriter
from iptv_manager.infrastructure.sources.channel_order_file import parse_channel_order_file
from iptv_manager.infrastructure.sources.local_file_source import LocalFilePlaylistSource
from iptv_manager.infrastructure.sources.playlist_bundles_file import parse_playlist_bundles_file
from iptv_manager.infrastructure.sources.remote_url_source import RemoteUrlPlaylistSource
from iptv_manager.infrastructure.sources.sources_file import parse_sources_file
from iptv_manager.infrastructure.validators.http_stream_validator import HttpStreamValidator
from iptv_manager.infrastructure.validators.logo_validator import LogoImageValidator

app = typer.Typer(help="IPTV Playlist Management & Validation System CLI")

class _ReportWriter(Protocol):
    def __init__(self) -> None: ...
    def write(self, report: ValidationReport, path: Path) -> None: ...


_REPORT_WRITERS: dict[str, tuple[str, type[_ReportWriter]]] = {
    "html": ("report.html", HTMLReportWriter),
    "json": ("report.json", JSONReportWriter),
    "csv": ("report.csv", CSVReportWriter),
    "xlsx": ("report.xlsx", ExcelReportWriter),
}


def _is_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


@app.command("import")
def import_category(
    category: str = typer.Argument(..., help="Category name, e.g. 'sports'"),
    source: str = typer.Argument(..., help="Local file path or http(s) URL to an M3U playlist"),
) -> None:
    """Import a playlist from a local file or URL into
    data/categories/<category>.m3u, normalizing it in the process."""
    settings = get_settings()
    settings.ensure_directories()

    parser = M3UParser()
    use_case = ImportPlaylistUseCase(parser=parser)

    playlist_source = (
        RemoteUrlPlaylistSource(
            source, timeout=settings.validation_timeout_seconds, user_agent=settings.user_agent
        )
        if _is_url(source)
        else LocalFilePlaylistSource(source)
    )

    playlist = asyncio.run(use_case.execute(playlist_source, category=category))

    output_path = settings.categories_path / f"{category}.m3u"
    output_path.write_text(parser.serialize(playlist), encoding="utf-8")

    typer.echo(f"Imported {len(playlist)} channel(s) into {output_path}")
    for warning in playlist.warnings:
        typer.echo(f"  warning: {warning}")


@app.command("sync-sources")
def sync_sources() -> None:
    """Re-import every category listed in data/sources.txt from its
    remote URL, overwriting only that category's own file under
    data/categories/. Categories not listed in sources.txt (e.g.
    manually curated playlists) are never touched.

    Safe to run on a schedule (see .github/workflows/pipeline.yml):
    one source failing to fetch is reported and skipped, it doesn't
    abort the sync for the others, and it doesn't fail the whole
    command (exit code 0) unless every configured source failed.
    """
    settings = get_settings()
    settings.ensure_directories()

    sources_path = settings.project_root / "data" / "sources.txt"
    entries = parse_sources_file(sources_path)

    if not entries:
        typer.echo(f"No sources configured in {sources_path} - nothing to sync.")
        return

    parser = M3UParser()
    use_case = SyncSourcesUseCase(
        parser=parser,
        timeout_seconds=settings.validation_timeout_seconds,
        user_agent=settings.user_agent,
    )
    result, serialized_by_name = asyncio.run(use_case.execute(entries))

    for name, text in serialized_by_name.items():
        output_path = settings.categories_path / f"{name}.m3u"
        output_path.write_text(text, encoding="utf-8")

    for entry in result.succeeded:
        typer.echo(f"  ok    {entry.name}: {entry.channel_count} channel(s) from {entry.url}")
    for entry in result.failed:
        typer.echo(f"  FAIL  {entry.name}: {entry.error} ({entry.url})", err=True)

    typer.echo(
        f"Synced {len(result.succeeded)}/{len(entries)} source(s)."
    )
    if result.failed and not result.succeeded:
        raise typer.Exit(code=1)


def _load_category_playlists(
    settings: Settings, parser: M3UParser
) -> tuple[list[Path], list[Playlist]]:
    category_files = sorted(
        set(settings.categories_path.glob("*.m3u")) | set(settings.categories_path.glob("*.m3u8"))
    )
    playlists: list[Playlist] = []
    for path in category_files:
        source = LocalFilePlaylistSource(path)
        raw_text = asyncio.run(source.fetch())
        playlists.append(parser.parse(raw_text, name=path.stem, category=path.stem))
    return category_files, playlists


def _merge_and_publish(settings: Settings, parser: M3UParser) -> tuple[int, MergeResult]:
    """Shared by `merge` and `report`: load every category file, merge
    ALL of them into one comprehensive result (used for validation and
    the report - every channel that exists anywhere gets checked),
    then additionally publish one or more curated "bundles" per
    data/playlists.txt (falling back to a single bundle containing
    everything if that file doesn't exist).

    Returns the comprehensive (all-categories) MergeResult - callers
    that only care about validation/reporting can ignore that bundles
    were published at all.
    """
    category_files, playlists = _load_category_playlists(settings, parser)

    if not category_files:
        typer.echo(f"No category playlists found in {settings.categories_path}", err=True)
        raise typer.Exit(code=1)

    playlists_by_stem = {
        path.stem: playlist
        for path, playlist in zip(category_files, playlists, strict=True)
    }

    order_path = settings.project_root / "data" / "channel_order.txt"
    priority_slots = parse_channel_order_file(order_path)

    # The comprehensive merge: every category, used for validation and
    # the report so nothing ever goes unchecked just because it was
    # left out of a bundle.
    everything_result = MergePlaylistsUseCase().execute(playlists, master_name="master")
    everything_result.master = BackfillTvgIdFromExactNameUseCase().execute(everything_result.master)
    everything_result.master = CategorizeByCountryUseCase().execute(everything_result.master)
    if priority_slots:
        everything_result.master = ApplyChannelOrderUseCase().execute(
            priority_slots, everything_result.master
        )

    bundles_path = settings.project_root / "data" / "playlists.txt"
    bundle_stems = parse_playlist_bundles_file(bundles_path)
    if not bundle_stems:
        # No playlists.txt - historical behavior: one "master" bundle
        # with every category file, published to the same paths as
        # before this feature existed.
        _publish_bundle(settings, parser, "master", everything_result.master)
        return len(category_files), everything_result

    for bundle_name, stems in bundle_stems.items():
        bundle_playlists = []
        for stem in stems:
            playlist = playlists_by_stem.get(stem)
            if playlist is None:
                typer.echo(
                    f"  warning: playlists.txt bundle {bundle_name!r} references unknown "
                    f"category {stem!r} (no data/categories/{stem}.m3u) - skipped",
                    err=True,
                )
                continue
            bundle_playlists.append(playlist)

        bundle_result = MergePlaylistsUseCase().execute(bundle_playlists, master_name=bundle_name)
        bundle_result.master = BackfillTvgIdFromExactNameUseCase().execute(bundle_result.master)
        bundle_result.master = CategorizeByCountryUseCase().execute(bundle_result.master)
        if priority_slots:
            bundle_result.master = ApplyChannelOrderUseCase().execute(
                priority_slots, bundle_result.master
            )
        _publish_bundle(settings, parser, bundle_name, bundle_result.master)
        typer.echo(
            f"  bundle {bundle_name!r}: {len(bundle_result.master)} channel(s) "
            f"from {len(bundle_playlists)}/{len(stems)} categor(y/ies)"
        )

    return len(category_files), everything_result


def _publish_bundle(
    settings: Settings, parser: M3UParser, bundle_name: str, master: Playlist
) -> None:
    """Write one bundle's merged playlist to data/master/<name>.m3u
    and, if Pages publishing is enabled, docs/<name>.m3u."""
    output_path = settings.master_path / f"{bundle_name}.m3u"
    serialized = parser.serialize(master, epg_url=settings.epg_url)
    output_path.write_text(serialized, encoding="utf-8")
    if settings.publish_target in (PublishTarget.PAGES_ONLY, PublishTarget.BOTH):
        docs_path = settings.project_root / settings.docs_dir / f"{bundle_name}.m3u"
        docs_path.write_text(serialized, encoding="utf-8")


@app.command("merge")
def merge_categories() -> None:
    """Merge every category playlist under data/categories/ into a
    single master playlist, removing exact-duplicate stream URLs, and
    publish it to data/master/master.m3u (and docs/master.m3u for
    GitHub Pages, depending on IPTV_PUBLISH_TARGET)."""
    settings = get_settings()
    settings.ensure_directories()

    parser = M3UParser()
    file_count, result = _merge_and_publish(settings, parser)

    typer.echo(f"Merged {file_count} category playlist(s)")
    typer.echo(f"Channels before dedup: {result.total_channels_before}")
    typer.echo(f"Channels after dedup:  {result.total_channels_after}")
    typer.echo(f"Duplicate URLs removed: {result.removed_duplicate_url_count}")
    typer.echo(f"Duplicate tvg-id groups (kept, flagged): {len(result.duplicate_tvg_ids)}")
    for group in result.duplicate_tvg_ids:
        names = ", ".join(c.name for c in group.channels)
        typer.echo(f"  tvg-id={group.tvg_id!r} shared by: {names}")
    for warning in result.master.warnings:
        typer.echo(f"  warning: {warning}")


@app.command("validate")
def validate_streams() -> None:
    """Validate every stream in the current master.m3u: HTTP status,
    redirects, response time, timeout/SSL/DNS errors, and geo
    restriction. Reads data/master/master.m3u (run `merge` first)."""
    settings = get_settings()

    if not settings.master_playlist_path.is_file():
        typer.echo(
            f"No master playlist found at {settings.master_playlist_path}. "
            "Run `iptv-manager merge` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    parser = M3UParser()
    raw_text = settings.master_playlist_path.read_text(encoding="utf-8")
    playlist = parser.parse(raw_text, name="master")

    validator = HttpStreamValidator(
        timeout_seconds=settings.validation_timeout_seconds,
        max_concurrency=settings.validation_max_concurrency,
        user_agent=settings.user_agent,
        retries=settings.validation_retries,
    )
    summary = asyncio.run(ValidateStreamsUseCase(validator=validator).execute(playlist))

    typer.echo(f"Validated {summary.total} stream(s)")
    typer.echo(f"  online:  {summary.online_count}")
    for status in StreamStatus:
        if status is StreamStatus.ONLINE:
            continue
        count = summary.count_by_status(status)
        if count:
            typer.echo(f"  {status.value}: {count}")
            for result in summary.filter_by_status(status):
                typer.echo(
                    f"    - {result.channel.name}: {result.error_message or result.http_status}"
                )


@app.command("check-logos")
def check_logos() -> None:
    """Validate every channel's logo (tvg-logo) URL in the current
    master.m3u, reporting missing vs unreachable logos separately."""
    settings = get_settings()

    if not settings.master_playlist_path.is_file():
        typer.echo(
            f"No master playlist found at {settings.master_playlist_path}. "
            "Run `iptv-manager merge` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    parser = M3UParser()
    raw_text = settings.master_playlist_path.read_text(encoding="utf-8")
    playlist = parser.parse(raw_text, name="master")

    validator = LogoImageValidator(
        timeout_seconds=settings.validation_timeout_seconds,
        max_concurrency=settings.validation_max_concurrency,
        user_agent=settings.user_agent,
    )
    summary = asyncio.run(ValidateLogosUseCase(validator=validator).execute(playlist))

    typer.echo(f"Checked {summary.total} channel(s)")
    typer.echo(f"  reachable:   {summary.reachable_count}")
    typer.echo(f"  missing:     {summary.missing_count}")
    typer.echo(f"  unreachable: {summary.unreachable_count}")


def _is_url_generic(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


@app.command("check-epg")
def check_epg(
    xmltv_source: str = typer.Argument(
        ..., help="Local file path or http(s) URL to an XMLTV file"
    ),
) -> None:
    """Compare the current master.m3u's tvg-id values against an XMLTV
    EPG file, reporting missing/invalid/duplicate tvg-ids and unused
    EPG entries."""
    settings = get_settings()

    if not settings.master_playlist_path.is_file():
        typer.echo(
            f"No master playlist found at {settings.master_playlist_path}. "
            "Run `iptv-manager merge` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    m3u_parser = M3UParser()
    playlist = m3u_parser.parse(
        settings.master_playlist_path.read_text(encoding="utf-8"), name="master"
    )

    epg_source = (
        RemoteUrlPlaylistSource(
            xmltv_source,
            timeout=settings.validation_timeout_seconds,
            user_agent=settings.user_agent,
        )
        if _is_url_generic(xmltv_source)
        else LocalFilePlaylistSource(xmltv_source)
    )
    raw_xmltv = asyncio.run(epg_source.fetch())
    epg_channels = XMLTVParser().parse(raw_xmltv)

    result = CompareWithXMLTVUseCase().execute(playlist, epg_channels)

    typer.echo(f"EPG channels loaded: {len(epg_channels)}")
    typer.echo(f"Missing tvg-id:    {len(result.missing_tvg_id)}")
    for channel in result.missing_tvg_id:
        typer.echo(f"  - {channel.name}")
    typer.echo(f"Invalid tvg-id:    {len(result.invalid_tvg_id)}")
    for channel in result.invalid_tvg_id:
        typer.echo(f"  - {channel.name} (tvg-id={channel.tvg_id})")
    typer.echo(f"Duplicate tvg-id:  {len(result.duplicate_tvg_id)}")
    for group in result.duplicate_tvg_id:
        names = ", ".join(c.name for c in group.channels)
        typer.echo(f"  - tvg-id={group.tvg_id!r}: {names}")
    typer.echo(f"Unused EPG entries: {len(result.unused_epg_entries)}")


@app.command("report")
def generate_report(
    formats: str = typer.Option(
        "html,json,csv,xlsx", "--formats", help="Comma-separated: html,json,csv,xlsx"
    ),
    epg_source: str = typer.Option(
        "", "--epg", help="Optional local file path or http(s) URL to an XMLTV file"
    ),
    skip_streams: bool = typer.Option(
        False, "--skip-streams", help="Skip stream validation (faster, e.g. for quick re-merges)"
    ),
    skip_logos: bool = typer.Option(False, "--skip-logos", help="Skip logo validation"),
) -> None:
    """Run the full pipeline - merge categories, validate streams,
    validate logos, and (if --epg is given) compare against an XMLTV
    EPG - then write the results to reports/ in every requested
    format. This is the single command GitHub Actions calls."""
    settings = get_settings()
    settings.ensure_directories()

    parser = M3UParser()
    file_count, merge_result = _merge_and_publish(settings, parser)
    typer.echo(
        f"Merged {file_count} category playlist(s): "
        f"{merge_result.total_channels_before} -> {merge_result.total_channels_after} channels"
    )

    stream_summary: StreamValidationSummary | None = None
    if not skip_streams:
        validator = HttpStreamValidator(
            timeout_seconds=settings.validation_timeout_seconds,
            max_concurrency=settings.validation_max_concurrency,
            user_agent=settings.user_agent,
            retries=settings.validation_retries,
        )
        stream_summary = asyncio.run(
            ValidateStreamsUseCase(validator=validator).execute(merge_result.master)
        )
        typer.echo(
            f"Validated streams: {stream_summary.online_count}/{stream_summary.total} online"
        )

    logo_summary: LogoValidationSummary | None = None
    if not skip_logos:
        logo_validator = LogoImageValidator(
            timeout_seconds=settings.validation_timeout_seconds,
            max_concurrency=settings.validation_max_concurrency,
            user_agent=settings.user_agent,
        )
        logo_summary = asyncio.run(
            ValidateLogosUseCase(validator=logo_validator).execute(merge_result.master)
        )
        typer.echo(
            f"Checked logos: {logo_summary.reachable_count}/{logo_summary.total} reachable"
        )

    epg_comparison = None
    if epg_source:
        source = (
            RemoteUrlPlaylistSource(
                epg_source,
                timeout=settings.validation_timeout_seconds,
                user_agent=settings.user_agent,
            )
            if _is_url_generic(epg_source)
            else LocalFilePlaylistSource(epg_source)
        )
        raw_xmltv = asyncio.run(source.fetch())
        epg_channels = XMLTVParser().parse(raw_xmltv)
        merge_result.master = MatchTvgIdFromEpgUseCase().execute(merge_result.master, epg_channels)
        epg_comparison = CompareWithXMLTVUseCase().execute(merge_result.master, epg_channels)
        # tvg-id may have just changed above - re-serialize master.m3u
        # (already written once inside _merge_and_publish) so the
        # newly-filled tvg-ids actually reach the published file.
        updated_master_text = parser.serialize(merge_result.master, epg_url=settings.epg_url)
        settings.master_playlist_path.write_text(updated_master_text, encoding="utf-8")
        if settings.publish_target in (PublishTarget.PAGES_ONLY, PublishTarget.BOTH):
            settings.docs_master_playlist_path.write_text(updated_master_text, encoding="utf-8")
        typer.echo(
            f"Compared against {len(epg_channels)} EPG channel(s): "
            f"{len(epg_comparison.invalid_tvg_id)} invalid tvg-id, "
            f"{len(epg_comparison.unused_epg_entries)} unused EPG entries"
        )

    report: ValidationReport = GenerateReportUseCase().execute(
        master_playlist_name="master",
        merge_result=merge_result,
        stream_summary=stream_summary,
        logo_summary=logo_summary,
        epg_comparison=epg_comparison,
    )

    requested_formats = [f.strip().lower() for f in formats.split(",") if f.strip()]
    unknown = set(requested_formats) - set(_REPORT_WRITERS)
    if unknown:
        typer.echo(f"Unknown format(s): {', '.join(sorted(unknown))}", err=True)
        raise typer.Exit(code=1)

    reports_dir = settings.project_root / settings.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    for fmt in requested_formats:
        filename, writer_cls = _REPORT_WRITERS[fmt]
        output_path: Path = reports_dir / filename
        writer_cls().write(report, output_path)
        typer.echo(f"Wrote {output_path}")


@app.command("serve")
def serve(
    host: str = typer.Option("", "--host", help="Override IPTV_API_HOST"),
    port: int = typer.Option(0, "--port", help="Override IPTV_API_PORT"),
) -> None:
    """Start the REST API + read-only dashboard (and, if
    IPTV_SCHEDULER_ENABLED=true, the background scheduler) with
    uvicorn. This is for self-hosted deployments; GitHub Actions
    deployments don't need this command at all."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "iptv_manager.interfaces.api.app:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
    )


if __name__ == "__main__":
    app()
