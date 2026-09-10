"""Unit tests for application.use_cases.sync_sources.

No real network calls: RemoteUrlPlaylistSource.fetch() is monkeypatched
per-test to return controlled text.
"""

from iptv_manager.application.use_cases.sync_sources import SyncSourcesUseCase
from iptv_manager.infrastructure.parsers.m3u_parser import M3UParser
from iptv_manager.infrastructure.sources.remote_url_source import (
    PlaylistFetchError,
    RemoteUrlPlaylistSource,
)
from iptv_manager.infrastructure.sources.sources_file import SourceEntry

RAW_WITH_MESSY_METADATA = (
    '#EXTM3U url-tvg="https://example.com/epg.xml.gz" x-custom="keep-me"\n'
    '#EXTINF:-1   group-title="📺  Nasional  " tvg-id="X.id",Some Channel\n'
    "http://example.com/stream/x.m3u8\n"
)


async def test_returns_the_source_raw_text_verbatim(monkeypatch):
    async def fake_fetch(self: RemoteUrlPlaylistSource) -> str:
        return RAW_WITH_MESSY_METADATA

    monkeypatch.setattr(RemoteUrlPlaylistSource, "fetch", fake_fetch)
    use_case = SyncSourcesUseCase(parser=M3UParser())

    result, texts_by_name = await use_case.execute(
        [SourceEntry(name="mysource", url="http://example.com/list.m3u")]
    )

    assert result.succeeded[0].name == "mysource"
    assert texts_by_name["mysource"] == RAW_WITH_MESSY_METADATA


async def test_reports_an_accurate_channel_count_without_altering_the_saved_text(monkeypatch):
    async def fake_fetch(self: RemoteUrlPlaylistSource) -> str:
        return RAW_WITH_MESSY_METADATA

    monkeypatch.setattr(RemoteUrlPlaylistSource, "fetch", fake_fetch)
    use_case = SyncSourcesUseCase(parser=M3UParser())

    result, _texts_by_name = await use_case.execute(
        [SourceEntry(name="mysource", url="http://example.com/list.m3u")]
    )

    assert result.succeeded[0].channel_count == 1


async def test_one_failing_source_does_not_affect_others(monkeypatch):
    async def fetch_dispatch(self: RemoteUrlPlaylistSource) -> str:
        if "bad" in self._url:
            raise PlaylistFetchError("simulated network failure")
        return RAW_WITH_MESSY_METADATA

    monkeypatch.setattr(RemoteUrlPlaylistSource, "fetch", fetch_dispatch)
    use_case = SyncSourcesUseCase(parser=M3UParser())

    result, texts_by_name = await use_case.execute(
        [
            SourceEntry(name="good", url="http://example.com/good.m3u"),
            SourceEntry(name="bad", url="http://example.com/bad.m3u"),
        ]
    )

    assert [r.name for r in result.succeeded] == ["good"]
    assert [r.name for r in result.failed] == ["bad"]
    assert texts_by_name == {"good": RAW_WITH_MESSY_METADATA}
