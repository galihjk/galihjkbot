from __future__ import annotations

import hashlib

import httpx
import pytest

from app.modules.autoreply.exceptions import (
    AutoreplySourceFetchError,
    AutoreplySourceTooLargeError,
)
from app.modules.autoreply.sources.google_sheet import GoogleSheetRuleSource


def _source(transport: httpx.MockTransport, max_bytes: int = 1024) -> GoogleSheetRuleSource:
    return GoogleSheetRuleSource(
        "https://example.com/sheet.csv",
        connect_timeout_seconds=1,
        read_timeout_seconds=1,
        max_bytes=max_bytes,
        transport=transport,
    )


async def test_fetch_success_returns_checksum_and_metadata():
    body = b"Command,Message\nhalo,hai\n"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"etag": "abc", "last-modified": "today"}
        )

    source = _source(httpx.MockTransport(handler))
    result = await source.fetch()

    assert result.content == body
    assert result.checksum == hashlib.sha256(body).hexdigest()
    assert result.etag == "abc"
    assert result.last_modified == "today"
    assert result.http_status == 200


async def test_fetch_too_large_raises_without_retry():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"x" * 2000)

    source = _source(httpx.MockTransport(handler), max_bytes=10)
    with pytest.raises(AutoreplySourceTooLargeError):
        await source.fetch()
    assert calls == 1


async def test_fetch_4xx_does_not_retry():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404, content=b"not found")

    source = _source(httpx.MockTransport(handler))
    with pytest.raises(AutoreplySourceFetchError):
        await source.fetch()
    assert calls == 1


async def test_fetch_5xx_retries_then_raises():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, content=b"boom")

    source = _source(httpx.MockTransport(handler))
    with pytest.raises(AutoreplySourceFetchError):
        await source.fetch()
    assert calls == 2


async def test_fetch_5xx_then_success_recovers():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, content=b"boom")
        return httpx.Response(200, content=b"ok")

    source = _source(httpx.MockTransport(handler))
    result = await source.fetch()
    assert result.content == b"ok"
    assert calls == 2
