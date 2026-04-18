import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)
STRAVA_SUBSCRIPTIONS_URL = "https://www.strava.com/api/v3/push_subscriptions"


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
    return settings.strava_client_id in ("", "test-client-id")


def _is_local_callback() -> bool:
    url = settings.strava_webhook_callback_url
    return "localhost" in url or "127.0.0.1" in url


async def _get_existing(client: httpx.AsyncClient) -> dict | None:
    response = await client.get(
        STRAVA_SUBSCRIPTIONS_URL,
        params={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
        },
    )
    subs = response.json()
    return subs[0] if isinstance(subs, list) and subs else None


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
        sub = response.json()
        logger.info("Strava webhook registered: id=%s callback=%s", sub["id"], sub["callback_url"])
    else:
        logger.warning(
            "Strava webhook registration returned %s: %s",
            response.status_code,
            response.text,
        )


async def _delete(client: httpx.AsyncClient, sub_id: int) -> None:
    await client.delete(
        f"{STRAVA_SUBSCRIPTIONS_URL}/{sub_id}",
        params={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
        },
    )
    logger.info("deleted stale Strava webhook subscription: id=%s", sub_id)
