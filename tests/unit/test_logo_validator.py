"""Unit tests for infrastructure.validators.logo_validator."""

import aiohttp
import pytest
from aioresponses import aioresponses
from aiohttp.client_reqrep import ConnectionKey

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.value_objects.group_title import GroupTitle
from iptv_manager.domain.value_objects.stream_url import StreamUrl
from iptv_manager.infrastructure.validators.logo_validator import LogoImageValidator

LOGO_URL = "http://cdn.example.com/logos/espn.png"


def _channel_with_logo(logo_url: str | None) -> Channel:
    return Channel(
        name="ESPN",
        url=StreamUrl.parse("http://provider.example.com/stream.m3u8"),
        logo_url=logo_url,
        group_title=GroupTitle.parse("Sports"),
    )


@pytest.mark.asyncio
async def test_missing_logo_reported_as_missing_not_unreachable():
    validator = LogoImageValidator()
    result = await validator.validate(_channel_with_logo(None))
    assert result.reachable is False
    assert result.error_message == "no logo_url set"


@pytest.mark.asyncio
async def test_reachable_logo_via_head():
    with aioresponses() as mocked:
        mocked.head(LOGO_URL, status=200)
        validator = LogoImageValidator()
        result = await validator.validate(_channel_with_logo(LOGO_URL))

    assert result.reachable is True
    assert result.http_status == 200


@pytest.mark.asyncio
async def test_head_405_falls_back_to_get():
    with aioresponses() as mocked:
        mocked.head(LOGO_URL, status=405)
        mocked.get(LOGO_URL, status=200)
        validator = LogoImageValidator()
        result = await validator.validate(_channel_with_logo(LOGO_URL))

    assert result.reachable is True


@pytest.mark.asyncio
async def test_404_logo_is_unreachable():
    with aioresponses() as mocked:
        mocked.head(LOGO_URL, status=404)
        validator = LogoImageValidator()
        result = await validator.validate(_channel_with_logo(LOGO_URL))

    assert result.reachable is False
    assert result.http_status == 404


@pytest.mark.asyncio
async def test_connection_error_is_unreachable():
    key = ConnectionKey(
        host="cdn.example.com",
        port=80,
        is_ssl=False,
        ssl=None,
        proxy=None,
        proxy_auth=None,
        proxy_headers_hash=None,
    )
    connector_error = aiohttp.ClientConnectorError(key, ConnectionRefusedError())

    with aioresponses() as mocked:
        mocked.head(LOGO_URL, exception=connector_error)
        validator = LogoImageValidator()
        result = await validator.validate(_channel_with_logo(LOGO_URL))

    assert result.reachable is False
    assert result.error_message is not None
