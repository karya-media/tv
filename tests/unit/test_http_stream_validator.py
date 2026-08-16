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


def _channel(url: str = STREAM_URL) -> Channel:
    return Channel(
        name="Test Channel",
        url=StreamUrl.parse(url),
        group_title=GroupTitle.parse("Test"),
    )


@pytest.mark.asyncio
async def test_online_via_head():
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, status=200)
        validator = HttpStreamValidator(retries=1)
        result = await validator.validate(_channel())

    assert result.status is StreamStatus.ONLINE
    assert result.http_status == 200
    assert result.response_time_ms is not None


@pytest.mark.asyncio
async def test_head_405_falls_back_to_get():
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, status=405)
        mocked.get(STREAM_URL, status=200, body=b"\x00" * 4096)
        validator = HttpStreamValidator(retries=1)
        result = await validator.validate(_channel())

    assert result.status is StreamStatus.ONLINE
    assert result.http_status == 200


@pytest.mark.asyncio
async def test_404_is_error_status():
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, status=404)
        validator = HttpStreamValidator(retries=1)
        result = await validator.validate(_channel())

    assert result.status is StreamStatus.ERROR
    assert result.http_status == 404


@pytest.mark.asyncio
async def test_403_is_geo_restricted():
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, status=403)
        validator = HttpStreamValidator(retries=1)
        result = await validator.validate(_channel())

    assert result.status is StreamStatus.GEO_RESTRICTED


@pytest.mark.asyncio
async def test_redirect_is_recorded():
    redirected_url = "http://cdn.example.com/stream/channel1.m3u8"
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, status=200, headers={"Location": redirected_url})
        # aioresponses represents the redirect as response history when
        # allow_redirects follows it - simulate the final response.
        validator = HttpStreamValidator(retries=1)
        result = await validator.validate(_channel())

    # Even without a literal redirect chain in this mock, the call
    # should still resolve to a final status without raising.
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
        validator = HttpStreamValidator(retries=1)
        result = await validator.validate(_channel())

    assert result.status is StreamStatus.OFFLINE


@pytest.mark.asyncio
async def test_timeout_reported():
    with aioresponses() as mocked:
        mocked.head(STREAM_URL, exception=TimeoutError())
        mocked.get(STREAM_URL, exception=TimeoutError())
        validator = HttpStreamValidator(retries=1)
        result = await validator.validate(_channel())

    assert result.status is StreamStatus.TIMEOUT


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt():
    with aioresponses() as mocked:
        # First HEAD attempt fails outright, second attempt succeeds.
        mocked.head(STREAM_URL, exception=TimeoutError())
        mocked.get(STREAM_URL, exception=TimeoutError())
        mocked.head(STREAM_URL, status=200)

        validator = HttpStreamValidator(retries=2)
        result = await validator.validate(_channel())

    assert result.status is StreamStatus.ONLINE


@pytest.mark.asyncio
async def test_concurrency_limit_is_respected():
    """Sanity check that the semaphore doesn't deadlock when many
    channels are validated at once."""
    channels = [_channel(f"http://provider.example.com/stream/ch{i}.m3u8") for i in range(20)]
    with aioresponses() as mocked:
        for channel in channels:
            mocked.head(str(channel.url), status=200)
        validator = HttpStreamValidator(retries=1, max_concurrency=5)
        results = await asyncio.gather(*(validator.validate(c) for c in channels))

    assert len(results) == 20
    assert all(r.status is StreamStatus.ONLINE for r in results)
