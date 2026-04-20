"""Webhook subscription registration tests.

The webhook subscription registration ran once at server startup. If Strava
returned 429 (rate limit), the code silently logged a warning and moved on
with no subscription registered — so every activity the user uploaded
afterwards was dropped on the floor because Strava had nowhere to POST.

These tests lock in:
  1. A transient 429 on the GET (existing-subscription check) is retried.
  2. After max retries on a hard 429, status is recorded as FAILED so
     /health can surface the outage to ops.
  3. On success, status is REGISTERED with the subscription id.
"""

import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.services import webhook_subscription as ws


def _response(status: int, body: object, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=body,
        headers=headers or {},
        request=httpx.Request("GET", "https://www.strava.com/api/v3/push_subscriptions"),
    )


def _settings_with_public_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ws.settings, "strava_client_id", "226140")
    monkeypatch.setattr(ws.settings, "strava_client_secret", "real-secret")
    monkeypatch.setattr(ws.settings, "strava_verify_token", "real-verify-token")
    monkeypatch.setattr(
        ws.settings,
        "strava_webhook_callback_url",
        "https://backend-production.up.railway.app/webhook/strava",
    )


def test_get_429_then_200_retries_and_finds_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Startup's GET hit 429; after retry we discover the matching sub."""
    _settings_with_public_url(monkeypatch)

    async def run() -> None:
        calls = {"n": 0}

        async def fake_get(self, url, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return _response(429, {"message": "Rate Limit Exceeded"}, {"Retry-After": "0"})
            return _response(
                200,
                [{"id": 555, "callback_url": ws.settings.strava_webhook_callback_url}],
            )

        async def noop_sleep(_s: float) -> None:
            return None

        with patch.object(httpx.AsyncClient, "get", fake_get), patch.object(
            ws.asyncio, "sleep", noop_sleep
        ):
            status = await ws.ensure_webhook_subscription()

        assert calls["n"] == 2
        assert status.state == "registered"
        assert status.subscription_id == 555

    asyncio.run(run())


def test_get_persistent_429_records_failed_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the GET never recovers, status is FAILED — /health must see it."""
    _settings_with_public_url(monkeypatch)

    async def run() -> None:
        async def always_429(self, url, **kwargs):
            return _response(429, {"message": "Rate Limit Exceeded"}, {"Retry-After": "0"})

        async def noop_sleep(_s: float) -> None:
            return None

        with patch.object(httpx.AsyncClient, "get", always_429), patch.object(
            ws.asyncio, "sleep", noop_sleep
        ):
            status = await ws.ensure_webhook_subscription()

        assert status.state == "failed"
        assert "429" in (status.error or "")

    asyncio.run(run())


def test_registers_when_no_existing_subscription(monkeypatch: pytest.MonkeyPatch) -> None:
    """Common case: no subscription yet, POST succeeds with id."""
    _settings_with_public_url(monkeypatch)

    async def run() -> None:
        async def empty_get(self, url, **kwargs):
            return _response(200, [])

        async def create_post(self, url, **kwargs):
            return _response(
                201,
                {"id": 777, "callback_url": ws.settings.strava_webhook_callback_url},
            )

        with patch.object(httpx.AsyncClient, "get", empty_get), patch.object(
            httpx.AsyncClient, "post", create_post
        ):
            status = await ws.ensure_webhook_subscription()

        assert status.state == "registered"
        assert status.subscription_id == 777


    asyncio.run(run())


def test_local_callback_reports_skipped_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Localhost URLs are dev mode — skipped, not failed."""
    monkeypatch.setattr(ws.settings, "strava_client_id", "226140")
    monkeypatch.setattr(ws.settings, "strava_client_secret", "real-secret")
    monkeypatch.setattr(ws.settings, "strava_verify_token", "real-verify-token")
    monkeypatch.setattr(
        ws.settings, "strava_webhook_callback_url", "http://localhost:8000/webhook/strava"
    )

    async def run() -> None:
        status = await ws.ensure_webhook_subscription()
        assert status.state == "skipped"
        assert "localhost" in (status.reason or "")

    asyncio.run(run())
