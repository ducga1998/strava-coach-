"""One-shot ops script: re-register the Strava webhook subscription, then
backfill recent activities for every athlete with a live credential.

Run this on Railway after the Strava daily read rate limit has reset:

    railway ssh --service backend python /app/scripts/reregister_and_backfill.py

Why this exists: during a period where our daily Strava read quota was
exhausted, the app startup silently failed to register the webhook and
two activities the user uploaded went unnoticed. With the fix in place,
server restart re-registers on its own — but activities that landed in
Strava during the outage still need a manual backfill.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Allow running either as `python scripts/reregister_and_backfill.py` from
# /app or as `python -m scripts.reregister_and_backfill`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import get_session_factory  # noqa: E402
from app.models.athlete import Athlete  # noqa: E402
from app.services.webhook_subscription import ensure_webhook_subscription  # noqa: E402
from app.workers.tasks import enqueue_backfill  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("reregister_and_backfill")


async def main() -> int:
    status = await ensure_webhook_subscription()
    logger.info("webhook subscription status: %s", status)
    if status.state != "registered":
        logger.error("registration did not succeed — aborting backfill")
        return 1

    async with get_session_factory()() as session:
        athletes = (await session.execute(select(Athlete))).scalars().all()

    if not athletes:
        logger.warning("no athletes in DB — nothing to backfill")
        return 0

    for athlete in athletes:
        logger.info(
            "backfilling recent activities for athlete=%s strava_id=%s",
            athlete.id,
            athlete.strava_athlete_id,
        )
        await enqueue_backfill(athlete.id)
    logger.info("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
