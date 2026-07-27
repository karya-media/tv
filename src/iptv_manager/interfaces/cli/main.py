"""CLI entrypoints, primarily invoked by GitHub Actions workflows
(wired in Phase 4) but equally usable by hand.

Commands:
    iptv-manager import CATEGORY SOURCE   - import one category playlist
    iptv-manager merge                    - merge all categories into master.m3u
"""

from __future__ import annotations

import asyncio

import typer

from iptv_manager.application.use_cases.import_playlist import ImportPlaylistUseCase
from iptv_manager.application.use_cases.merge_playlists import MergePlaylistsUseCase
from iptv_manager.config.settings import PublishTarget, get_settings
from iptv_manager.infrastructure.parsers.m3u_parser import M3UParser
from iptv_manager.infrastructure.sources.local_file_source import LocalFilePlaylistSource
from iptv_manager.infrastructure.sources.remote_url_source import RemoteUrlPlaylistSource

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


if __name__ == "__main__":
    app()
