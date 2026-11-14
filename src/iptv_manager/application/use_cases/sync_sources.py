"""Use case: re-import every category listed in data/sources.txt from
its remote URL, overwriting only that category's own file.

Each feed is isolated: a bad provider must not abort the others, and
manually maintained category files are never touched.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from iptv_manager.application.use_cases.import_playlist import ImportPlaylistUseCase
from iptv_manager.domain.ports.playlist_parser import PlaylistParser
from iptv_manager.infrastructure.parsers.json_parser import JSONPlaylistParser
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
        """Fetch all sources and return outcome plus M3U content by name.

        M3U sources are retained byte-for-byte. JSON feeds are normalized
        to M3U before writing: downstream merge loads category files with
        M3UParser, so saving the original JSON under a .m3u filename would
        make those channels disappear at merge time.
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

            if _looks_like_json(raw_text):
                output_text = JSONPlaylistParser().serialize(playlist)
            else:
                output_text = raw_text

            serialized_by_name[entry.name] = output_text
            result.results.append(
                SourceSyncResult(
                    name=entry.name,
                    url=entry.url,
                    success=True,
                    channel_count=len(playlist),
                )
            )

        return result, serialized_by_name


def _looks_like_json(raw_text: str) -> bool:
    stripped = raw_text.lstrip().lstrip("\ufeff")
    return bool(stripped) and stripped[0] in "[{"
