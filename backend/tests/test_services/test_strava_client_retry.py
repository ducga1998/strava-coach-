"""Retry-on-429 regression tests for the Strava client.

A webhook-triggered ingestion path that silently drops activities on a
transient Strava 429 is how a whole evening's runs can go missing.
The client should absorb short-window rate limits and only surface the
error if the backoff budget truly exhausts.
"""

import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.services import strava_client as sc
from app.services.strava_client import StravaClient


def _json_response(status_code: int, body: object, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=body,
        headers=headers or {},
        request=httpx.Request("GET", "https://www.strava.com/api/v3/ping"),
    )


def test_429_then_200_retries_and_succeeds() -> None:
    """One transient 429 followed by 200 should succeed, not raise."""

    async def run() -> None:
        calls = {"n": 0}

        async def fake_send(self, method, url, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return _json_response(429, {"message": "Rate Limit Exceeded"}, {"Retry-After": "0"})
            return _json_response(200, {"ok": True})

        async def noop_sleep(_s: float) -> None:
            return None

        with patch.object(StravaClient, "_send_once", fake_send), patch.object(
            sc, "asyncio", type("M", (), {"sleep": noop_sleep})
        ):
            client = StravaClient()
            resp = await client._request("GET", "https://www.strava.com/api/v3/ping")
            assert resp.status_code == 200
            assert calls["n"] == 2

    asyncio.run(run())


def test_429_exhausts_retries_and_raises() -> None:
    """Persistent 429 (e.g. daily cap) surfaces as HTTPStatusError once we
    run out of attempts — callers (e.g. webhook background task) should log
    and requeue rather than trying forever."""

    async def run() -> None:
        async def always_429(self, method, url, **kwargs):
            return _json_response(429, {"message": "Rate Limit Exceeded"}, {"Retry-After": "0"})

        async def noop_sleep(_s: float) -> None:
            return None

        with patch.object(StravaClient, "_send_once", always_429), patch.object(
            sc, "asyncio", type("M", (), {"sleep": noop_sleep})
        ):
            client = StravaClient()
            with pytest.raises(httpx.HTTPStatusError) as ei:
                await client._request("GET", "https://www.strava.com/api/v3/ping")
            assert ei.value.response.status_code == 429

    asyncio.run(run())


def test_non_429_error_does_not_retry() -> None:
    """A 500 should surface immediately — retrying a server error burns
    Strava's quota without helping."""

    async def run() -> None:
        calls = {"n": 0}

        async def always_500(self, method, url, **kwargs):
            calls["n"] += 1
            return _json_response(500, {"error": "boom"})

        with patch.object(StravaClient, "_send_once", always_500):
            client = StravaClient()
            with pytest.raises(httpx.HTTPStatusError):
                await client._request("GET", "https://www.strava.com/api/v3/ping")
            assert calls["n"] == 1

    asyncio.run(run())


def test_retry_delay_honours_retry_after_header() -> None:
    resp = _json_response(429, {}, {"Retry-After": "7"})
    assert sc._retry_delay_seconds(resp, attempt=0) == 7.0


def test_retry_delay_caps_retry_after() -> None:
    """A ludicrous Retry-After (e.g. 3600s daily reset) is capped so we at
    least retry once within a sane background-task lifetime."""
    resp = _json_response(429, {}, {"Retry-After": "9999"})
    assert sc._retry_delay_seconds(resp, attempt=0) == sc._RETRY_MAX_BACKOFF_SEC


def test_retry_delay_falls_back_to_exponential() -> None:
    resp = _json_response(429, {}, {})
    d0 = sc._retry_delay_seconds(resp, attempt=0)
    d1 = sc._retry_delay_seconds(resp, attempt=1)
    d2 = sc._retry_delay_seconds(resp, attempt=2)
    assert d0 < d1 < d2
    assert d2 <= sc._RETRY_MAX_BACKOFF_SEC
