"""Fetch behavior tests for remote URL sources."""

import httpx
import pytest

from iptv_manager.infrastructure.sources.remote_url_source import RemoteUrlPlaylistSource


@pytest.mark.asyncio
async def test_fetch_tries_next_user_agent_after_http_error(monkeypatch):
    seen_agents: list[str] = []
    original_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        user_agent = request.headers["user-agent"]
        seen_agents.append(user_agent)
        if user_agent == "OTT Navigator/1.7.5.1":
            return httpx.Response(404, request=request)
        return httpx.Response(200, text='{"channels": []}', request=request)

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    source = RemoteUrlPlaylistSource("https://example.test/", user_agent="Configured UA")

    assert await source.fetch() == '{"channels": []}'
    assert seen_agents == ["OTT Navigator/1.7.5.1", "Configured UA"]


@pytest.mark.asyncio
async def test_fetch_skips_html_landing_page_and_tries_next_user_agent(monkeypatch):
    seen_agents: list[str] = []
    original_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        user_agent = request.headers["user-agent"]
        seen_agents.append(user_agent)
        if user_agent == "OTT Navigator/1.7.5.1":
            return httpx.Response(200, text="<!doctype html><html></html>", request=request)
        return httpx.Response(200, text="#EXTM3U\n", request=request)

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    source = RemoteUrlPlaylistSource("https://example.test/", user_agent="Configured UA")

    assert await source.fetch() == "#EXTM3U\n"
    assert seen_agents == ["OTT Navigator/1.7.5.1", "Configured UA"]
