#!/usr/bin/env python3
"""
Webhook end-to-end test script.

Tests the Strava webhook pipeline in two modes:

  Mode 1 – Simulate (no Strava auth required):
      Fires fake webhook POSTs straight to the production endpoint.
      Use this to check the endpoint is reachable and responds 200.

  Mode 2 – Real activity (Strava token required):
      Creates a real manual activity via the Strava API, then
      watches for the webhook event to arrive at the backend by
      polling the backend DB/activity endpoint.

Usage:
    # Simulate only (default)
    python scripts/test_webhook.py

    # Simulate against local server
    python scripts/test_webhook.py --url http://localhost:8000

    # Full flow: create real activity and watch pipeline
    python scripts/test_webhook.py --real --token YOUR_STRAVA_ACCESS_TOKEN

    # Get a token from the DB (requires DB access)
    python scripts/test_webhook.py --real --from-db --athlete-id 124897781
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import httpx

# ---------------------------------------------------------------------------
# Config (override with env vars or CLI flags)
# ---------------------------------------------------------------------------
BACKEND_URL = os.getenv(
    "BACKEND_URL", "https://backend-production-3f79.up.railway.app"
)
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "226140")
STRAVA_CLIENT_SECRET = os.getenv(
    "STRAVA_CLIENT_SECRET", "09fbe2423794de292e9d5a6d402028ecb76d07f3"
)
WEBHOOK_SUBSCRIPTION_ID = int(os.getenv("WEBHOOK_SUBSCRIPTION_ID", "341264"))
STRAVA_API = "https://www.strava.com/api/v3"
DB_PUBLIC_URL = os.getenv(
    "DATABASE_PUBLIC_URL",
    "postgresql://postgres:OTzVzlqIaoBIdMJbBsPdIoEFvnQpDLnM@maglev.proxy.rlwy.net:56723/railway",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def ok(msg: str) -> None:
    print(f"  \033[92m✓\033[0m {msg}")


def fail(msg: str) -> None:
    print(f"  \033[91m✗\033[0m {msg}")


def info(msg: str) -> None:
    print(f"  \033[94m→\033[0m {msg}")


def header(msg: str) -> None:
    print(f"\n\033[1m{msg}\033[0m")


# ---------------------------------------------------------------------------
# Step 1 – Subscription health check
# ---------------------------------------------------------------------------
def check_subscription() -> bool:
    header("1. Checking Strava webhook subscription")
    r = httpx.get(
        f"{STRAVA_API}/push_subscriptions",
        params={"client_id": STRAVA_CLIENT_ID, "client_secret": STRAVA_CLIENT_SECRET},
        timeout=10,
    )
    subs = r.json()
    if not isinstance(subs, list) or not subs:
        fail("No active webhook subscription found on Strava")
        info("Run: python scripts/register_webhook.py")
        return False
    sub = subs[0]
    ok(f"Subscription id={sub['id']} callback={sub['callback_url']}")
    if sub["callback_url"] != f"{BACKEND_URL}/webhook/strava":
        fail(
            f"callback_url mismatch! Strava has: {sub['callback_url']}\n"
            f"  Expected: {BACKEND_URL}/webhook/strava"
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Step 2 – Backend health
# ---------------------------------------------------------------------------
def check_backend_health(base_url: str) -> bool:
    header("2. Checking backend health")
    try:
        r = httpx.get(f"{base_url}/health", timeout=10)
        if r.status_code == 200:
            ok(f"{base_url}/health → {r.json()}")
            return True
        fail(f"Health returned {r.status_code}")
        return False
    except Exception as e:
        fail(f"Cannot reach backend: {e}")
        return False


# ---------------------------------------------------------------------------
# Step 3 – Simulate webhook events
# ---------------------------------------------------------------------------
FAKE_ATHLETE_ID = 124897781  # your Strava athlete ID
FAKE_ACTIVITY_ID = 99999999999  # non-existent – just tests endpoint response


def simulate_event(base_url: str, payload: dict) -> bool:
    r = httpx.post(
        f"{base_url}/webhook/strava",
        json=payload,
        timeout=10,
    )
    if r.status_code == 200:
        ok(f"{payload['aspect_type']} {payload['object_type']} → 200 {r.json()}")
        return True
    fail(f"{payload['aspect_type']} {payload['object_type']} → {r.status_code} {r.text}")
    return False


def simulate_all_events(base_url: str) -> bool:
    header("3. Simulating webhook events (fake payloads)")
    now = int(time.time())
    events = [
        {
            "object_type": "activity",
            "object_id": FAKE_ACTIVITY_ID,
            "aspect_type": "create",
            "owner_id": FAKE_ATHLETE_ID,
            "subscription_id": WEBHOOK_SUBSCRIPTION_ID,
            "event_time": now,
            "updates": {},
        },
        {
            "object_type": "activity",
            "object_id": FAKE_ACTIVITY_ID,
            "aspect_type": "update",
            "owner_id": FAKE_ATHLETE_ID,
            "subscription_id": WEBHOOK_SUBSCRIPTION_ID,
            "event_time": now,
            "updates": {"title": "Test update"},
        },
        {
            "object_type": "activity",
            "object_id": FAKE_ACTIVITY_ID,
            "aspect_type": "delete",
            "owner_id": FAKE_ATHLETE_ID,
            "subscription_id": WEBHOOK_SUBSCRIPTION_ID,
            "event_time": now,
            "updates": {},
        },
    ]
    return all(simulate_event(base_url, e) for e in events)


# ---------------------------------------------------------------------------
# Step 4 – Real activity flow
# ---------------------------------------------------------------------------
def get_token_from_db(athlete_id: int) -> str | None:
    """Fetch + decrypt access token from production DB."""
    try:
        import psycopg2
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import base64

        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key:
            fail("ENCRYPTION_KEY env var not set — cannot decrypt token from DB")
            return None

        conn = psycopg2.connect(DB_PUBLIC_URL)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT sc.access_token_enc, sc.expires_at, sc.refresh_token_enc
            FROM strava_credentials sc
            JOIN athletes a ON a.id = sc.athlete_id
            WHERE a.strava_athlete_id = %s
            """,
            (athlete_id,),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            fail(f"No credentials found for athlete {athlete_id}")
            return None

        access_enc, expires_at, refresh_enc = row
        now = int(time.time())

        if expires_at < now + 300:
            info("Token expired — refreshing via Strava...")
            key = base64.b64decode(encryption_key)
            aesgcm = AESGCM(key)
            enc_bytes = base64.b64decode(refresh_enc)
            nonce, ct = enc_bytes[:12], enc_bytes[12:]
            refresh_token = aesgcm.decrypt(nonce, ct, None).decode()

            r = httpx.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": STRAVA_CLIENT_ID,
                    "client_secret": STRAVA_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                timeout=15,
            )
            r.raise_for_status()
            return r.json()["access_token"]

        key = base64.b64decode(encryption_key)
        aesgcm = AESGCM(key)
        enc_bytes = base64.b64decode(access_enc)
        nonce, ct = enc_bytes[:12], enc_bytes[12:]
        return aesgcm.decrypt(nonce, ct, None).decode()

    except Exception as e:
        fail(f"DB token fetch failed: {e}")
        return None


def create_real_activity(token: str) -> int | None:
    """Create a manual activity on Strava, return its ID."""
    start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = httpx.post(
        f"{STRAVA_API}/activities",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"[test] Webhook test {int(time.time())}",
            "sport_type": "Run",
            "start_date_local": start,
            "elapsed_time": 1800,       # 30 min
            "description": "Auto-created by test_webhook.py — safe to delete",
            "distance": 5000,           # 5 km
            "trainer": False,
            "commute": False,
        },
        timeout=15,
    )
    if r.status_code == 201:
        activity = r.json()
        ok(f"Created activity id={activity['id']} name='{activity['name']}'")
        return activity["id"]
    fail(f"Failed to create activity: {r.status_code} {r.text}")
    return None


def poll_backend_for_activity(base_url: str, athlete_id: int, strava_activity_id: int, timeout_s: int = 90) -> bool:
    """Poll DB every 5s until the activity appears (ingestion pipeline ran)."""
    info(f"Polling DB for strava_activity_id={strava_activity_id} (up to {timeout_s}s)…")
    try:
        import psycopg2
        db_url = os.getenv("DATABASE_PUBLIC_URL")
        if not db_url:
            info("DATABASE_PUBLIC_URL not set — falling back to backend poll")
            return _poll_via_backend(base_url, athlete_id, strava_activity_id, timeout_s)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute(
                "SELECT processing_status, skipped_reason FROM activities WHERE strava_activity_id = %s",
                (strava_activity_id,),
            )
            row = cur.fetchone()
            conn.close()
            if row:
                status, reason = row
                ok(f"Activity in DB: status={status} reason={reason}")
                return True
            time.sleep(5)
            sys.stdout.write(".")
            sys.stdout.flush()
        print()
        fail(f"Activity {strava_activity_id} not found in DB after {timeout_s}s — webhook may be delayed")
        info("Strava can take 1-5 min to dispatch webhook events for manual activities")
        return False
    except ImportError:
        return _poll_via_backend(base_url, athlete_id, strava_activity_id, timeout_s)


def _poll_via_backend(base_url: str, athlete_id: int, strava_activity_id: int, timeout_s: int) -> bool:
    """Fallback: list endpoint filter by athlete and scan for the strava id."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = httpx.get(f"{base_url}/activities/", params={"athlete_id": athlete_id}, timeout=10)
        if r.status_code == 200:
            for act in r.json():
                if act.get("strava_activity_id") == strava_activity_id:
                    ok(f"Activity found via list: status={act.get('processing_status')}")
                    return True
        time.sleep(5)
        sys.stdout.write(".")
        sys.stdout.flush()
    print()
    fail(f"Activity {strava_activity_id} not found after {timeout_s}s")
    return False


def delete_test_activity(token: str, activity_id: int) -> None:
    """Clean up the test activity from Strava."""
    r = httpx.delete(
        f"{STRAVA_API}/activities/{activity_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if r.status_code == 204:
        ok(f"Deleted test activity {activity_id} from Strava")
    elif r.status_code == 401:
        info(
            f"Could not delete activity {activity_id}: 401 — token lacks activity:write scope. "
            "Re-authorize via /auth/strava to get the updated scope, then delete manually."
        )
    else:
        info(f"Could not delete activity {activity_id}: {r.status_code}")


def run_real_flow(base_url: str, token: str, athlete_id: int) -> None:
    header("4. Full real-activity flow")
    activity_id = create_real_activity(token)
    if not activity_id:
        return
    info("Waiting 10s for Strava to dispatch webhook event…")
    time.sleep(10)
    found = poll_backend_for_activity(base_url, athlete_id, activity_id)
    if not found:
        info(f"Manual check: curl {base_url}/activities/{activity_id}?athlete_id={athlete_id}")
    info("Cleaning up test activity from Strava…")
    delete_test_activity(token, activity_id)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Strava webhook test script")
    parser.add_argument("--url", default=BACKEND_URL, help="Backend base URL")
    parser.add_argument("--real", action="store_true", help="Run real-activity flow")
    parser.add_argument("--token", help="Strava access token (for --real mode)")
    parser.add_argument("--from-db", action="store_true", help="Fetch token from production DB")
    parser.add_argument("--athlete-id", type=int, default=FAKE_ATHLETE_ID)
    args = parser.parse_args()

    base_url = args.url.rstrip("/")

    print("\n\033[1m=== Strava Webhook Test ===\033[0m")
    print(f"  Backend : {base_url}")
    print(f"  Athlete : {args.athlete_id}")

    all_ok = True
    all_ok &= check_subscription()
    all_ok &= check_backend_health(base_url)
    all_ok &= simulate_all_events(base_url)

    if args.real:
        token = args.token
        if not token and args.from_db:
            header("4a. Fetching token from production DB")
            token = get_token_from_db(args.athlete_id)
        if not token:
            fail("No token provided. Use --token or --from-db.")
            sys.exit(1)
        run_real_flow(base_url, token, args.athlete_id)

    header("Summary")
    if all_ok:
        ok("All checks passed")
    else:
        fail("Some checks failed — review output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
