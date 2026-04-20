import asyncio
import logging
from dataclasses import dataclass
from typing import Literal, TypedDict

import httpx

from app.config import settings
from app.services.strava_client import _RETRY_MAX_ATTEMPTS, _retry_delay_seconds

logger = logging.getLogger(__name__)
STRAVA_SUBSCRIPTIONS_URL = "https://www.strava.com/api/v3/push_subscriptions"


class StravaSubscription(TypedDict):
    id: int
    callback_url: str


SubscriptionState = Literal["registered", "failed", "skipped", "unknown"]


@dataclass(frozen=True)
class SubscriptionStatus:
    """Observable outcome of ensure_webhook_subscription.

    Stored in app.state so /health can report whether Strava can actually
    deliver webhooks — the original silent failure mode hid a full day of
    lost activities.
    """

    state: SubscriptionState
    subscription_id: int | None = None
    callback_url: str | None = None
    reason: str | None = None
    error: str | None = None


UNKNOWN_STATUS = SubscriptionStatus(state="unknown")


async def ensure_webhook_subscription() -> SubscriptionStatus:
    if _is_test_config():
        logger.debug("skipping Strava webhook registration: test credentials")
        return SubscriptionStatus(state="skipped", reason="test credentials")
    if _is_local_callback():
        logger.warning(
            "skipping Strava webhook registration: callback URL is localhost "
            "(%s). Set STRAVA_WEBHOOK_CALLBACK_URL to a public HTTPS URL.",
            settings.strava_webhook_callback_url,
        )
        return SubscriptionStatus(
            state="skipped",
            reason=f"localhost callback URL: {settings.strava_webhook_callback_url}",
        )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            existing = await _get_existing(client)
            if existing and existing["callback_url"] == settings.strava_webhook_callback_url:
                logger.info("Strava webhook already registered: id=%s", existing["id"])
                return SubscriptionStatus(
                    state="registered",
                    subscription_id=existing["id"],
                    callback_url=existing["callback_url"],
                )
            if existing:
                await _delete(client, existing["id"])
            return await _register(client)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Strava webhook registration failed: HTTP %s %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return SubscriptionStatus(
            state="failed",
            error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
        )
    except Exception as exc:  # noqa: BLE001 — startup hook must not crash app
        logger.warning("Strava webhook registration failed", exc_info=True)
        return SubscriptionStatus(state="failed", error=repr(exc))


def _is_test_config() -> bool:
    test_values = {"", "test-client-id", "test-client-secret", "test-verify-token"}
    return (
        settings.strava_client_id in test_values
        or settings.strava_client_secret in test_values
        or settings.strava_verify_token in test_values
    )


def _is_local_callback() -> bool:
    url = settings.strava_webhook_callback_url
    return "localhost" in url or "127.0.0.1" in url


async def _get_existing(client: httpx.AsyncClient) -> StravaSubscription | None:
    response = await _send_with_retry(
        client,
        "GET",
        STRAVA_SUBSCRIPTIONS_URL,
        params={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
        },
    )
    response.raise_for_status()
    return _parse_subscription(response.json())


async def _register(client: httpx.AsyncClient) -> SubscriptionStatus:
    response = await _send_with_retry(
        client,
        "POST",
        STRAVA_SUBSCRIPTIONS_URL,
        data={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            "callback_url": settings.strava_webhook_callback_url,
            "verify_token": settings.strava_verify_token,
        },
    )
    if response.status_code == 201:
        sub = _parse_created_subscription(response.json())
        logger.info(
            "Strava webhook registered: id=%s callback=%s",
            sub["id"],
            sub["callback_url"],
        )
        return SubscriptionStatus(
            state="registered",
            subscription_id=sub["id"] or None,
            callback_url=sub["callback_url"] or None,
        )
    logger.warning(
        "Strava webhook registration returned %s: %s",
        response.status_code,
        response.text,
    )
    return SubscriptionStatus(
        state="failed",
        error=f"HTTP {response.status_code}: {response.text[:200]}",
    )


async def _delete(client: httpx.AsyncClient, sub_id: int) -> None:
    response = await _send_with_retry(
        client,
        "DELETE",
        f"{STRAVA_SUBSCRIPTIONS_URL}/{sub_id}",
        params={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
        },
    )
    response.raise_for_status()
    logger.info("deleted stale Strava webhook subscription: id=%s", sub_id)


async def _send_with_retry(
    client: httpx.AsyncClient, method: str, url: str, **kwargs: object
) -> httpx.Response:
    """Mirrors StravaClient._request: retry on 429 honouring Retry-After.

    The original bug: startup's GET to /push_subscriptions hit a transient
    429 and the whole registration was silently skipped. Absorbing short
    rate-limit bursts prevents that. A persistent 429 still surfaces.
    """
    for attempt in range(_RETRY_MAX_ATTEMPTS):
        response = await _send_once(client, method, url, **kwargs)
        if response.status_code != 429 or attempt == _RETRY_MAX_ATTEMPTS - 1:
            return response
        delay = _retry_delay_seconds(response, attempt)
        logger.warning(
            "Strava webhook 429 on %s %s — retry %d/%d in %.1fs",
            method,
            url,
            attempt + 1,
            _RETRY_MAX_ATTEMPTS - 1,
            delay,
        )
        await asyncio.sleep(delay)
    return response  # pragma: no cover — loop always returns above


async def _send_once(
    client: httpx.AsyncClient, method: str, url: str, **kwargs: object
) -> httpx.Response:
    method_upper = method.upper()
    if method_upper == "GET":
        return await client.get(url, **kwargs)
    if method_upper == "POST":
        return await client.post(url, **kwargs)
    if method_upper == "DELETE":
        return await client.delete(url, **kwargs)
    raise ValueError(f"unsupported method: {method}")


def _parse_subscription(payload: object) -> StravaSubscription | None:
    if not isinstance(payload, list) or not payload:
        return None
    first = payload[0]
    if not isinstance(first, dict):
        return None
    sub_id = first.get("id")
    callback_url = first.get("callback_url")
    if not isinstance(sub_id, int) or not isinstance(callback_url, str):
        return None
    return {"id": sub_id, "callback_url": callback_url}


def _parse_created_subscription(payload: object) -> StravaSubscription:
    if not isinstance(payload, dict):
        return {"id": 0, "callback_url": settings.strava_webhook_callback_url}
    sub_id = payload.get("id")
    callback_url = payload.get("callback_url", settings.strava_webhook_callback_url)
    return {
        "id": sub_id if isinstance(sub_id, int) else 0,
        "callback_url": callback_url if isinstance(callback_url, str) else "",
    }
