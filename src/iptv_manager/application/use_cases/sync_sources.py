"""Use case: re-import every category listed in data/sources.txt from
its remote URL, overwriting only that category's own file.

Deliberately isolated per entry: one provider being down or returning
garbage must not abort the sync for every other source, and must not
touch category files that aren't in sources.txt at all (that's how
manually curated categories stay untouched by automation).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from iptv_manager.application.use_cases.import_playlist import ImportPlaylistUseCase
from iptv_manager.domain.ports.playlist_parser import PlaylistParser
from iptv_manager.infrastructure.sources.remote_url_source import (
    PlaylistFetchError,
    RemoteUrlPlaylistSource,
)
from iptv_manager.infrastructure.sources.sources_file import SourceEntry


@dataclass(slots=True)
class SourceSyncResult:
    name: str
    url: str
    success: bool
    channel_count: int = 0
    error: str | None = None


@dataclass(slots=True)
class SyncSourcesResult:
    results: list[SourceSyncResult] = field(default_factory=list)

    @property
    def succeeded(self) -> list[SourceSyncResult]:
        return [r for r in self.results if r.success]

    @property
    def failed(self) -> list[SourceSyncResult]:
        return [r for r in self.results if not r.success]


@dataclass(slots=True)
class SyncSourcesUseCase:
    parser: PlaylistParser
    timeout_seconds: float = 15.0
    user_agent: str = "IPTV-Playlist-Manager/0.1"

    async def execute(self, entries: list[SourceEntry]) -> tuple[SyncSourcesResult, dict[str, str]]:
        """Fetch every source. Returns the outcome summary alongside a
        {category_name: raw_m3u_text} map the caller writes to disk
        verbatim (see ImportPlaylistUseCase.execute()'s docstring for
        why this is the source's own untouched text, not a
        re-serialized reconstruction) - kept separate from disk I/O so
        this stays unit-testable.
        """
        result = SyncSourcesResult()
        serialized_by_name: dict[str, str] = {}
        import_use_case = ImportPlaylistUseCase(parser=self.parser)

        for entry in entries:
            source = RemoteUrlPlaylistSource(
                entry.url, timeout=self.timeout_seconds, user_agent=self.user_agent
            )
            try:
                raw_text, playlist = await import_use_case.execute(source, category=entry.name)
            except PlaylistFetchError as exc:
                result.results.append(
                    SourceSyncResult(name=entry.name, url=entry.url, success=False, error=str(exc))
                )
                continue
            except Exception as exc:  # noqa: BLE001 - one bad source must not kill the batch
                result.results.append(
                    SourceSyncResult(
                        name=entry.name,
                        url=entry.url,
                        success=False,
                        error=f"unexpected error: {exc}",
                    )
                )
                continue

            # Save the source's own raw text verbatim - not a
            # re-serialized reconstruction - so data/categories/*.m3u
            # stays byte-faithful to upstream (group-title text,
            # header attributes like url-tvg, attribute formatting,
            # everything). `playlist` here is parsed only to get an
            # accurate channel count for the summary below; it's never
            # written to disk.
            serialized_by_name[entry.name] = raw_text
            result.results.append(
                SourceSyncResult(
                    name=entry.name,
                    url=entry.url,
                    success=True,
                    channel_count=len(playlist),
                )
            )

        return result, serialized_by_name
