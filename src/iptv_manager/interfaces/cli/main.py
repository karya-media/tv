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
from collections.abc import Callable
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
from iptv_manager.application.use_cases.limit_channel_variants import (
    LimitChannelVariantsUseCase,
    online_urls_from_results,
)
from iptv_manager.application.use_cases.match_tvg_id_from_epg import MatchTvgIdFromEpgUseCase
from iptv_manager.application.use_cases.merge_epg_sources import MergeEPGSourcesUseCase
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
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.epg_channel import EPGChannel
from iptv_manager.domain.entities.epg_programme import EPGProgramme
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.entities.stream_validation_result import StreamStatus
from iptv_manager.infrastructure.parsers.m3u_parser import M3UParser
from iptv_manager.infrastructure.parsers.xmltv_parser import XMLTVParser
from iptv_manager.infrastructure.reports.csv_report_writer import CSVReportWriter
from iptv_manager.infrastructure.reports.excel_report_writer import ExcelReportWriter
from iptv_manager.infrastructure.reports.html_report_writer import HTMLReportWriter
from iptv_manager.infrastructure.reports.json_report_writer import JSONReportWriter
from iptv_manager.infrastructure.serializers.xmltv_writer import write_xmltv
from iptv_manager.infrastructure.sources.channel_order_file import parse_channel_order_file
from iptv_manager.infrastructure.sources.epg_sources_file import parse_epg_sources_file
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
    """Shared by `merge` and `report`: build the comprehensive
    (all-categories) result, then immediately publish every bundle
    from it.

    `report` calls _build_everything_result() and _publish_bundles()
    separately instead of this, so it can run stream validation,
    variant-limiting, and EPG matching on the comprehensive result
    *before* bundles are split out and written - otherwise a bundle's
    published file would reflect only the initial merge, not the
    fully-processed data those extra steps produce.
    """
    category_file_count, everything_result, publish = _build_everything_result(settings, parser)
    publish(everything_result)
    return category_file_count, everything_result


def _build_everything_result(
    settings: Settings, parser: M3UParser
) -> tuple[int, MergeResult, Callable[[MergeResult], None]]:
    """Load every category file and merge ALL of them into one
    comprehensive result (used for validation and the report - every
    channel that exists anywhere gets checked, and this is also what
    every bundle is ultimately built from).

    Returns (category_file_count, everything_result, publish) - call
    publish(everything_result) once you're done mutating
    everything_result.master (stream validation, variant-limiting,
    EPG matching, ...) to split it into and write every bundle from
    data/playlists.txt (falling back to a single "master" bundle
    containing everything if that file doesn't exist). Calling
    publish() more than once, or not at all, is a caller bug - do it
    exactly once, after all processing is finished.
    """
    category_files, playlists = _load_category_playlists(settings, parser)

    if not category_files:
        typer.echo(f"No category playlists found in {settings.categories_path}", err=True)
        raise typer.Exit(code=1)

    playlists_by_stem = {
        path.stem: playlist for path, playlist in zip(category_files, playlists, strict=True)
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

    def publish(result: MergeResult) -> None:
        _publish_bundles(
            settings, parser, result, category_files, playlists_by_stem, priority_slots
        )

    return len(category_files), everything_result, publish


def _publish_bundles(
    settings: Settings,
    parser: M3UParser,
    everything_result: MergeResult,
    category_files: list[Path],
    playlists_by_stem: dict[str, Playlist],
    priority_slots: list[list[str]],
) -> None:
    """Split everything_result.master into every bundle named in
    data/playlists.txt (stem-based, group:-based, "*", or any mix) and
    write each one out. See _build_everything_result()'s docstring for
    why this is a separate step instead of happening inline."""
    bundles_path = settings.project_root / "data" / "playlists.txt"
    bundle_specs = parse_playlist_bundles_file(bundles_path)
    if not bundle_specs:
        # No playlists.txt - historical behavior: one "master" bundle
        # with every category file, published to the same paths as
        # before this feature existed.
        _publish_bundle(settings, parser, "master", everything_result.master)
        return

    published_urls: set[str] = set()

    for bundle_name, spec in bundle_specs.items():
        if spec.all_stems:
            # "*" - every category stem, already fully processed as
            # part of everything_result.master. No need to re-merge.
            _publish_bundle(settings, parser, bundle_name, everything_result.master)
            published_urls.update(channel.url.raw for channel in everything_result.master)
            typer.echo(
                f"  bundle {bundle_name!r}: {len(everything_result.master)} channel(s) "
                f"(all {len(category_files)} categor(y/ies), via '*')"
            )
            continue

        bundle_playlists = []
        for stem in spec.stems:
            playlist = playlists_by_stem.get(stem)
            if playlist is None:
                typer.echo(
                    f"  warning: playlists.txt bundle {bundle_name!r} references unknown "
                    f"category {stem!r} (no data/categories/{stem}.m3u) - skipped",
                    err=True,
                )
                continue
            bundle_playlists.append(playlist)

        stem_channels: list[Channel] = []
        if bundle_playlists:
            stem_result = MergePlaylistsUseCase().execute(bundle_playlists, master_name=bundle_name)
            stem_result.master = BackfillTvgIdFromExactNameUseCase().execute(stem_result.master)
            stem_result.master = CategorizeByCountryUseCase().execute(stem_result.master)
            stem_channels = list(stem_result.master)

        # "group:<prefix>" entries pull matching channels straight
        # from everything_result.master - already fully processed
        # (backfilled, country-tagged, and - when called from `report`
        # - stream-validated/variant-limited/EPG-matched too), so
        # group-title matching is as accurate as it'll ever be,
        # regardless of which category file a channel happened to
        # come from.
        seen_urls = {channel.url.raw for channel in stem_channels}
        group_channels = [
            channel
            for channel in everything_result.master
            if channel.url.raw not in seen_urls
            and any(channel.group_title.matches_prefix(p) for p in spec.group_prefixes)
        ]

        bundle_channels = stem_channels + group_channels
        if not bundle_channels:
            typer.echo(f"  warning: bundle {bundle_name!r} matched no channels - skipped", err=True)
            continue

        bundle_master = Playlist(name=bundle_name, channels=bundle_channels)
        if priority_slots:
            bundle_master = ApplyChannelOrderUseCase().execute(priority_slots, bundle_master)

        _publish_bundle(settings, parser, bundle_name, bundle_master)
        published_urls.update(channel.url.raw for channel in bundle_master)
        typer.echo(
            f"  bundle {bundle_name!r}: {len(bundle_master)} channel(s) "
            f"({len(stem_channels)} from {len(bundle_playlists)}/{len(spec.stems)} "
            f"categor(y/ies), {len(group_channels)} from "
            f"{len(spec.group_prefixes)} group prefix(es))"
        )

    # A category file whose channels never made it into *any* published
    # bundle (neither by stem nor by a matching group prefix) is still
    # validated/reported on (everything_result covers it), but easy to
    # miss otherwise - flag it explicitly.
    orphaned_stems = sorted(
        stem
        for stem, playlist in playlists_by_stem.items()
        if playlist and not any(channel.url.raw in published_urls for channel in playlist)
    )
    if orphaned_stems:
        typer.echo(
            "  warning: these category file(s) aren't covered by any "
            f"data/playlists.txt bundle (by stem or group: prefix), so they won't "
            f"appear in any published playlist: {', '.join(orphaned_stems)}",
            err=True,
        )


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


async def _fetch_epg_content(
    source: RemoteUrlPlaylistSource | LocalFilePlaylistSource,
) -> str | bytes:
    """Fetch an XMLTV EPG source, preferring the memory-lighter bytes
    path (RemoteUrlPlaylistSource.fetch_bytes()) when available - a
    large aggregated EPG file decompressed and text-decoded twice over
    is the difference between this succeeding and the process being
    OOM-killed on a memory-constrained CI runner. LocalFilePlaylistSource
    has no such method (local files are assumed small); fall back to
    its normal str fetch() in that case."""
    if isinstance(source, RemoteUrlPlaylistSource):
        return await source.fetch_bytes()
    return await source.fetch()


@app.command("merge-epg")
def merge_epg() -> None:
    """Fetch every XMLTV source listed in data/epg_sources.txt *plus*
    any distinct url-tvg header found in data/categories/*.m3u files,
    combine them into one EPG (see MergeEPGSourcesUseCase), and write
    it to data/epg/epg.xml.

    Filtered to only the channels actually present in master.m3u -
    keeps the output small and safe to process, instead of repeating
    the out-of-memory problem a full multi-source aggregate (every
    channel in the world, not just the ones in this playlist) caused
    earlier in this project. Point IPTV_EPG_URL / the `epg_url`
    setting at this file's raw.githubusercontent.com URL once
    committed, to use it for master.m3u's "#EXTM3U url-tvg=..."
    header instead of a third-party source.
    """
    settings = get_settings()

    if not settings.master_playlist_path.is_file():
        typer.echo(
            f"No master playlist found at {settings.master_playlist_path}. "
            "Run `iptv-manager merge` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    m3u_parser = M3UParser()

    epg_sources_path = settings.project_root / "data" / "epg_sources.txt"
    urls = list(parse_epg_sources_file(epg_sources_path))

    # Auto-discover: any category file (data/categories/*.m3u) may
    # declare its own "#EXTM3U url-tvg=..." header - e.g. a
    # hand-curated or uploaded file that already names a preferred EPG
    # source. These are picked up automatically so the same URL never
    # has to be copied into epg_sources.txt by hand, and so a *new*
    # category file with a *different* declared source is honored
    # without any extra configuration step. Explicit epg_sources.txt
    # entries still come first (win on conflict); auto-discovered ones
    # are appended afterward, deduplicated by URL, in filename order.
    discovered: list[str] = []
    for category_path in sorted(settings.categories_path.glob("*.m3u")) + sorted(
        settings.categories_path.glob("*.m3u8")
    ):
        header_playlist = m3u_parser.parse(
            category_path.read_text(encoding="utf-8", errors="replace"), name=category_path.stem
        )
        if header_playlist.epg_url and header_playlist.epg_url not in urls:
            discovered.append(header_playlist.epg_url)
            typer.echo(f"Discovered EPG source in {category_path.name}: {header_playlist.epg_url}")
    for url in discovered:
        if url not in urls:
            urls.append(url)

    if not urls:
        typer.echo(
            f"No EPG sources found - none listed in {epg_sources_path}, and no "
            "data/categories/*.m3u file declares its own url-tvg header. Nothing to merge.",
            err=True,
        )
        raise typer.Exit(code=1)

    master = m3u_parser.parse(
        settings.master_playlist_path.read_text(encoding="utf-8"), name="master"
    )
    wanted_channel_ids = {channel.tvg_id.value for channel in master if channel.has_tvg_id}
    typer.echo(f"Wanted channel ids from master.m3u: {len(wanted_channel_ids)}")

    xmltv_parser = XMLTVParser()
    parsed_sources: list[tuple[list[EPGChannel], list[EPGProgramme]]] = []
    for url in urls:
        source: RemoteUrlPlaylistSource | LocalFilePlaylistSource = (
            RemoteUrlPlaylistSource(
                url, timeout=settings.epg_fetch_timeout_seconds, user_agent=settings.user_agent
            )
            if _is_url_generic(url)
            else LocalFilePlaylistSource(url)
        )
        try:
            raw_content = asyncio.run(_fetch_epg_content(source))
            channels, programmes = xmltv_parser.parse_channels_and_programmes(
                raw_content, wanted_channel_ids=wanted_channel_ids
            )
        except Exception as exc:  # noqa: BLE001 - one bad source must never sink the merge
            typer.echo(f"Skipped {url}: {exc}", err=True)
            continue
        typer.echo(f"{url}: {len(channels)} channel(s), {len(programmes)} programme(s)")
        parsed_sources.append((channels, programmes))

    if not parsed_sources:
        typer.echo("No EPG source could be fetched successfully.", err=True)
        raise typer.Exit(code=1)

    result = MergeEPGSourcesUseCase().execute(parsed_sources)
    typer.echo(
        f"Merged: {len(result.channels)} channel(s), {len(result.programmes)} programme(s)"
    )

    output_path = settings.epg_path / "epg.xml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(write_xmltv(result.channels, result.programmes))
    typer.echo(f"Wrote {output_path}")


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
            timeout=settings.epg_fetch_timeout_seconds,
            user_agent=settings.user_agent,
        )
        if _is_url_generic(xmltv_source)
        else LocalFilePlaylistSource(xmltv_source)
    )
    raw_xmltv = asyncio.run(_fetch_epg_content(epg_source))
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
    max_variants: int = typer.Option(
        2,
        "--max-variants",
        help=(
            "Cap each data/channel_order.txt family (e.g. RCTI, RCTI HD, RCTI 2, "
            "RCTI Vision+) to this many channels, preferring ones stream validation "
            "confirmed are online. 0 disables capping. Ignored with --skip-streams, "
            "since there'd be no playability signal to rank variants by."
        ),
    ),
) -> None:
    """Run the full pipeline - merge categories, validate streams,
    validate logos, and (if --epg is given) compare against an XMLTV
    EPG - then write the results to reports/ in every requested
    format. This is the single command GitHub Actions calls."""
    settings = get_settings()
    settings.ensure_directories()

    parser = M3UParser()
    file_count, merge_result, publish = _build_everything_result(settings, parser)
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

        if max_variants > 0:
            order_path = settings.project_root / "data" / "channel_order.txt"
            priority_slots = parse_channel_order_file(order_path)
            if priority_slots:
                before_count = len(merge_result.master)
                merge_result.master = LimitChannelVariantsUseCase().execute(
                    priority_slots,
                    merge_result.master,
                    online_urls=online_urls_from_results(stream_summary.results),
                    max_variants=max_variants,
                )
                dropped_count = before_count - len(merge_result.master)
                if dropped_count:
                    typer.echo(
                        f"Limited channel variants: dropped {dropped_count} extra "
                        f"copy/copies (kept up to {max_variants} per family, "
                        "preferring online ones)"
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
        try:
            source = (
                RemoteUrlPlaylistSource(
                    epg_source,
                    timeout=settings.epg_fetch_timeout_seconds,
                    user_agent=settings.user_agent,
                )
                if _is_url_generic(epg_source)
                else LocalFilePlaylistSource(epg_source)
            )
            raw_xmltv = asyncio.run(_fetch_epg_content(source))
            epg_channels = XMLTVParser().parse(raw_xmltv)
            merge_result.master = MatchTvgIdFromEpgUseCase().execute(
                merge_result.master, epg_channels
            )
            epg_comparison = CompareWithXMLTVUseCase().execute(merge_result.master, epg_channels)
            typer.echo(
                f"Compared against {len(epg_channels)} EPG channel(s): "
                f"{len(epg_comparison.invalid_tvg_id)} invalid tvg-id, "
                f"{len(epg_comparison.unused_epg_entries)} unused EPG entries"
            )
        except Exception as exc:  # noqa: BLE001 - EPG is best-effort, never fatal
            # A slow/unreachable/malformed third-party EPG source must
            # never take down the whole report - the merge/stream/logo
            # results above are still valid and worth publishing.
            typer.echo(f"EPG matching skipped due to an error: {exc}", err=True)
            epg_comparison = None

    # Every bundle is split out of and written from merge_result.master
    # *here*, now that stream validation, variant-limiting, and EPG
    # matching have all finished mutating it - so every published file
    # (master.m3u, and any other data/playlists.txt bundle) reflects
    # the fully-processed data, not just the initial merge.
    publish(merge_result)

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
