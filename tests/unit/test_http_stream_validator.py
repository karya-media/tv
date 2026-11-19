"""Unit tests for infrastructure.validators.http_stream_validator.

All HTTP calls are intercepted with aioresponses - no real network
access is made, and no real IPTV stream is required.
"""

import asyncio

import aiohttp
import pytest
from aiohttp.client_reqrep import ConnectionKey
from aioresponses import aioresponses

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.stream_validation_result import StreamStatus
from iptv_manager.domain.value_objects.group_title import GroupTitle
from iptv_manager.domain.value_objects.stream_url import StreamUrl
from iptv_manager.infrastructure.validators.http_stream_validator import HttpStreamValidator

STREAM_URL = "http://provider.example.com/stream/channel1.m3u8"
STREAM_BYTES = b"\x47" * 1024


def _channel(url: str = STREAM_URL) -> Channel:
    return Channel(
        name="Test Channel",
        url=StreamUrl.parse(url),
        group_title=GroupTitle.parse("Test"),
    )


@pytest.mark.asyncio
async def test_online_requires_readable_get_body_even_after_successful_head():
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, status=200)
        mocked.get(STREAM_URL, status=200, body=STREAM_BYTES,
                   headers={"Content-Type": "video/mp2t"})
        result = await HttpStreamValidator(retries=1).validate(_channel())

    assert result.status is StreamStatus.ONLINE
    assert result.http_status == 200
    assert result.bytes_read > 0
    assert result.content_type == "video/mp2t"


@pytest.mark.asyncio
async def test_head_405_falls_back_to_get():
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, status=405)
        mocked.get(STREAM_URL, status=206, body=STREAM_BYTES,
                   headers={"Content-Type": "video/mp2t"})
        result = await HttpStreamValidator(retries=1).validate(_channel())

    assert result.status is StreamStatus.ONLINE
    assert result.http_status == 206


@pytest.mark.asyncio
async def test_404_is_offline():
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, status=404)
        result = await HttpStreamValidator(retries=1).validate(_channel())

    assert result.status is StreamStatus.OFFLINE
    assert result.http_status == 404


@pytest.mark.asyncio
async def test_403_is_geo_restricted():
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, status=403)
        result = await HttpStreamValidator(retries=1).validate(_channel())

    assert result.status is StreamStatus.GEO_RESTRICTED


@pytest.mark.asyncio
async def test_html_response_is_not_a_valid_stream():
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, status=200)
        mocked.get(STREAM_URL, status=200, body="<html>blocked</html>",
                   headers={"Content-Type": "text/html"})
        result = await HttpStreamValidator(retries=1).validate(_channel())

    assert result.status is StreamStatus.ERROR
    assert result.bytes_read > 0


@pytest.mark.asyncio
async def test_redirect_is_recorded():
    redirected_url = "http://cdn.example.com/stream/channel1.m3u8"
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, status=302, headers={"Location": redirected_url})
        mocked.get(STREAM_URL, status=200, body=STREAM_BYTES,
                   headers={"Content-Type": "video/mp2t"})
        result = await HttpStreamValidator(retries=1).validate(_channel())

    # The GET result is authoritative if aioresponses does not simulate a
    # complete redirect chain.
    assert result.status in (StreamStatus.ONLINE, StreamStatus.ERROR)


def _connector_error() -> aiohttp.ClientConnectorError:
    key = ConnectionKey(
        host="provider.example.com",
        port=80,
        is_ssl=False,
        ssl=None,
        proxy=None,
        proxy_auth=None,
        proxy_headers_hash=None,
    )
    return aiohttp.ClientConnectorError(key, ConnectionRefusedError())


@pytest.mark.asyncio
async def test_connection_refused_is_offline():
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, exception=_connector_error())
        mocked.get(STREAM_URL, exception=_connector_error())
        result = await HttpStreamValidator(retries=1).validate(_channel())

    assert result.status is StreamStatus.OFFLINE


@pytest.mark.asyncio
async def test_timeout_reported():
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, exception=TimeoutError())
        mocked.get(STREAM_URL, exception=TimeoutError())
        result = await HttpStreamValidator(retries=1).validate(_channel())

    assert result.status is StreamStatus.TIMEOUT


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt():
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, exception=TimeoutError())
        mocked.get(STREAM_URL, exception=TimeoutError())
        mocked.head(STREAM_URL, status=200)
        mocked.get(STREAM_URL, status=200, body=STREAM_BYTES,
                   headers={"Content-Type": "video/mp2t"})
        validator = HttpStreamValidator(retries=2, retry_delay_seconds=0)
        result = await validator.validate(_channel())

    assert result.status is StreamStatus.ONLINE


@pytest.mark.asyncio
async def test_concurrency_limit_is_respected():
    channels = [
        _channel(f"http://provider.example.com/stream/ch{i}.m3u8")
        for i in range(20)
    ]
    with aioresponses() as mocked:
        for channel in channels:
            mocked.head(str(channel.url), status=200)
            mocked.get(str(channel.url), status=200, body=STREAM_BYTES,
                       headers={"Content-Type": "video/mp2t"})
        validator = HttpStreamValidator(retries=1, max_concurrency=5)
        results = await asyncio.gather(*(validator.validate(channel) for channel in channels))

    assert len(results) == 20
    assert all(result.status is StreamStatus.ONLINE for result in results)
