#!/usr/bin/env python3
"""Register or view the Strava webhook subscription.

Usage:
  python scripts/register_webhook.py            # register (reads from env or prompts)
  python scripts/register_webhook.py --view     # list existing subscriptions
  python scripts/register_webhook.py --delete   # delete existing subscription

Requires: STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_WEBHOOK_CALLBACK_URL,
          STRAVA_VERIFY_TOKEN (or will prompt).
"""

import asyncio
import os
import sys

import httpx

STRAVA_SUBSCRIPTIONS_URL = "https://www.strava.com/api/v3/push_subscriptions"


def _env(key: str, prompt: str) -> str:
    value = os.environ.get(key)
    if value:
        return value
    return input(f"{prompt}: ").strip()


def _load_config() -> dict[str, str]:
    return {
        "client_id": _env("STRAVA_CLIENT_ID", "STRAVA_CLIENT_ID"),
        "client_secret": _env("STRAVA_CLIENT_SECRET", "STRAVA_CLIENT_SECRET"),
        "callback_url": _env("STRAVA_WEBHOOK_CALLBACK_URL", "callback_url (public HTTPS)"),
        "verify_token": _env("STRAVA_VERIFY_TOKEN", "STRAVA_VERIFY_TOKEN"),
    }


async def register(cfg: dict[str, str]) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(STRAVA_SUBSCRIPTIONS_URL, data=cfg)
    if response.status_code == 201:
        sub = response.json()
        print(f"Subscription created: id={sub['id']}")
        print(f"  callback_url = {sub['callback_url']}")
    elif response.status_code == 409:
        print("Subscription already exists.")
        await view(cfg)
    else:
        print(f"Error {response.status_code}: {response.text}", file=sys.stderr)
        sys.exit(1)


async def view(cfg: dict[str, str]) -> None:
    params = {"client_id": cfg["client_id"], "client_secret": cfg["client_secret"]}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(STRAVA_SUBSCRIPTIONS_URL, params=params)
    subs = response.json()
    if not subs:
        print("No subscriptions found.")
        return
    for sub in subs:
        print(f"id={sub['id']}  callback_url={sub['callback_url']}")


async def delete(cfg: dict[str, str]) -> None:
    await view(cfg)
    sub_id = input("Enter subscription id to delete: ").strip()
    params = {"client_id": cfg["client_id"], "client_secret": cfg["client_secret"]}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.delete(
            f"{STRAVA_SUBSCRIPTIONS_URL}/{sub_id}", params=params
        )
    if response.status_code == 204:
        print(f"Subscription {sub_id} deleted.")
    else:
        print(f"Error {response.status_code}: {response.text}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--register"
    cfg = _load_config()
    if mode == "--view":
        asyncio.run(view(cfg))
    elif mode == "--delete":
        asyncio.run(delete(cfg))
    else:
        asyncio.run(register(cfg))


if __name__ == "__main__":
    main()
