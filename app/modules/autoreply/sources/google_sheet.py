from __future__ import annotations

import asyncio
import hashlib
import logging
import random

import httpx

from app.modules.autoreply.exceptions import (
    AutoreplySourceFetchError,
    AutoreplySourceTooLargeError,
)
from app.modules.autoreply.schemas import RawSource

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 2
_USER_AGENT = "TelegramMultiBot-AutoreplyMsgCmd/1.0"


class GoogleSheetRuleSource:
    """HTTP GET terhadap satu URL Google Sheet CSV terpublikasi yang tetap
    (dari config deployment, bukan input command) -- lihat §16.2/§24 desain:
    tidak ada retry pada 4xx, maksimum dua percobaan untuk timeout/5xx."""

    def __init__(
        self,
        url: str,
        *,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        max_bytes: int,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = url
        self._timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=read_timeout_seconds,
            pool=connect_timeout_seconds,
        )
        self._max_bytes = max_bytes
        # `transport` cuma dipakai test (httpx.MockTransport) untuk
        # menghindari panggilan jaringan sungguhan -- None di produksi.
        self._transport = transport

    async def fetch(self) -> RawSource:
        last_error: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                return await self._fetch_once()
            except AutoreplySourceTooLargeError:
                raise
            except AutoreplySourceFetchError as exc:
                last_error = exc
                if not exc.retryable or attempt >= _MAX_ATTEMPTS:
                    raise
                jitter = random.uniform(0.2, 0.6)
                logger.warning(
                    "Fetch autoreply source gagal (percobaan %s/%s), retry dalam %.2fs.",
                    attempt,
                    _MAX_ATTEMPTS,
                    jitter,
                )
                await asyncio.sleep(jitter)
        assert last_error is not None
        raise last_error

    async def _fetch_once(self) -> RawSource:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                max_redirects=5,
                verify=True,
                transport=self._transport,
            ) as client:
                response = await client.get(
                    self._url, headers={"User-Agent": _USER_AGENT}
                )
        except httpx.TimeoutException as exc:
            raise AutoreplySourceFetchError(
                f"Timeout mengambil source: {exc}", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise AutoreplySourceFetchError(
                f"Gagal mengambil source: {exc}", retryable=True
            ) from exc

        if response.status_code >= 500:
            raise AutoreplySourceFetchError(
                f"HTTP {response.status_code} dari source.", retryable=True
            )
        if response.status_code >= 400:
            raise AutoreplySourceFetchError(
                f"HTTP {response.status_code} dari source.", retryable=False
            )

        content = response.content
        if len(content) > self._max_bytes:
            raise AutoreplySourceTooLargeError(
                f"Ukuran source {len(content)} byte melebihi batas {self._max_bytes} byte."
            )

        checksum = hashlib.sha256(content).hexdigest()
        return RawSource(
            content=content,
            checksum=checksum,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
            http_status=response.status_code,
        )
