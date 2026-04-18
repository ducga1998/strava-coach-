import logging
from typing import TypedDict

import httpx

from app.config import settings

logger = logging.getLogger(__name__)
STRAVA_SUBSCRIPTIONS_URL = "https://www.strava.com/api/v3/push_subscriptions"


class StravaSubscription(TypedDict):
    id: int
    callback_url: str


async def ensure_webhook_subscription() -> None:
    if _is_test_config():
        logger.debug("skipping Strava webhook registration: test credentials")
        return
    if _is_local_callback():
        logger.warning(
            "skipping Strava webhook registration: callback URL is localhost "
            "(%s). Set STRAVA_WEBHOOK_CALLBACK_URL to a public HTTPS URL.",
            settings.strava_webhook_callback_url,
        )
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            existing = await _get_existing(client)
            if existing and existing["callback_url"] == settings.strava_webhook_callback_url:
                logger.info("Strava webhook already registered: id=%s", existing["id"])
                return
            if existing:
                await _delete(client, existing["id"])
            await _register(client)
    except Exception:
        logger.warning("Strava webhook registration failed (server still starting)", exc_info=True)


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
    response = await client.get(
        STRAVA_SUBSCRIPTIONS_URL,
        params={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
        },
    )
    response.raise_for_status()
    return _parse_subscription(response.json())


async def _register(client: httpx.AsyncClient) -> None:
    response = await client.post(
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
    else:
        logger.warning(
            "Strava webhook registration returned %s: %s",
            response.status_code,
            response.text,
        )


async def _delete(client: httpx.AsyncClient, sub_id: int) -> None:
    response = await client.delete(
        f"{STRAVA_SUBSCRIPTIONS_URL}/{sub_id}",
        params={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
        },
    )
    response.raise_for_status()
    logger.info("deleted stale Strava webhook subscription: id=%s", sub_id)


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
