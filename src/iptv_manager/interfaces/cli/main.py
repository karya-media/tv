"""CLI entrypoints, primarily invoked by GitHub Actions workflows
(wired in Phase 4) but equally usable by hand.

Commands:
    iptv-manager import CATEGORY SOURCE   - import one category playlist
    iptv-manager merge                    - merge all categories into master.m3u
    iptv-manager validate                 - validate every stream in master.m3u
    iptv-manager check-logos              - validate every channel's logo image
    iptv-manager check-epg XMLTV_SOURCE   - compare master.m3u tvg-ids against an XMLTV EPG
"""

from __future__ import annotations

import asyncio

import typer

from iptv_manager.application.use_cases.compare_with_xmltv import CompareWithXMLTVUseCase
from iptv_manager.application.use_cases.import_playlist import ImportPlaylistUseCase
from iptv_manager.application.use_cases.merge_playlists import MergePlaylistsUseCase
from iptv_manager.application.use_cases.validate_logos import ValidateLogosUseCase
from iptv_manager.application.use_cases.validate_streams import ValidateStreamsUseCase
from iptv_manager.config.settings import PublishTarget, get_settings
from iptv_manager.domain.entities.stream_validation_result import StreamStatus
from iptv_manager.infrastructure.parsers.m3u_parser import M3UParser
from iptv_manager.infrastructure.parsers.xmltv_parser import XMLTVParser
from iptv_manager.infrastructure.sources.local_file_source import LocalFilePlaylistSource
from iptv_manager.infrastructure.sources.remote_url_source import RemoteUrlPlaylistSource
from iptv_manager.infrastructure.validators.http_stream_validator import HttpStreamValidator
from iptv_manager.infrastructure.validators.logo_validator import LogoImageValidator

app = typer.Typer(help="IPTV Playlist Management & Validation System CLI")


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


@app.command("merge")
def merge_categories() -> None:
    """Merge every category playlist under data/categories/ into a
    single master playlist, removing exact-duplicate stream URLs, and
    publish it to data/master/master.m3u (and docs/master.m3u for
    GitHub Pages, depending on IPTV_PUBLISH_TARGET)."""
    settings = get_settings()
    settings.ensure_directories()

    parser = M3UParser()
    category_files = sorted(
        set(settings.categories_path.glob("*.m3u")) | set(settings.categories_path.glob("*.m3u8"))
    )

    if not category_files:
        typer.echo(f"No category playlists found in {settings.categories_path}", err=True)
        raise typer.Exit(code=1)

    playlists = []
    for path in category_files:
        source = LocalFilePlaylistSource(path)
        raw_text = asyncio.run(source.fetch())
        playlists.append(parser.parse(raw_text, name=path.stem, category=path.stem))

    result = MergePlaylistsUseCase().execute(playlists, master_name="master")

    settings.master_playlist_path.write_text(parser.serialize(result.master), encoding="utf-8")

    if settings.publish_target in (PublishTarget.PAGES_ONLY, PublishTarget.BOTH):
        settings.docs_master_playlist_path.write_text(
            parser.serialize(result.master), encoding="utf-8"
        )

    typer.echo(f"Merged {len(category_files)} category playlist(s)")
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


if __name__ == "__main__":
    app()
