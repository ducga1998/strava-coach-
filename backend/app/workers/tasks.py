import logging

from app.database import get_session_factory
from app.models.athlete import Athlete
from app.services.activity_ingestion import IngestionResult, backfill_recent_activities, ingest_activity
from app.services.plan_import import sync_plan
from app.services.strava_client import StravaClient
from app.services.token_service import get_token_service


logger = logging.getLogger(__name__)


async def enqueue_activity(
    strava_athlete_id: int, strava_activity_id: int
) -> IngestionResult:
    try:
        async with get_session_factory()() as session:
            result = await ingest_activity(
                session=session,
                strava_athlete_id=strava_athlete_id,
                strava_activity_id=strava_activity_id,
                client=StravaClient(),
                token_service=get_token_service(),
            )
    except Exception:
        logger.exception(
            "activity ingestion failed: athlete=%s activity=%s",
            strava_athlete_id,
            strava_activity_id,
        )
        return IngestionResult(status="failed")
    if result.reason is not None:
        logger.info("activity ingestion skipped: %s", result.reason)
    return result


async def enqueue_backfill(athlete_id: int) -> None:
    try:
        async with get_session_factory()() as session:
            count = await backfill_recent_activities(
                session=session,
                athlete_id=athlete_id,
                client=StravaClient(),
                token_service=get_token_service(),
            )
        logger.info("backfill complete: athlete=%s ingested=%s", athlete_id, count)
    except Exception:
        logger.exception("backfill failed: athlete=%s", athlete_id)


async def enqueue_plan_sync(athlete_id: int) -> None:
    """Autosync an athlete's training plan on an isolated DB session.

    Running on its own session means a failure (or sync_plan's internal
    commit) can never interfere with the caller's transaction — critical
    for the activity-ingestion path, which has half-processed activity
    state open on its own session. Failures are logged and swallowed.
    """
    try:
        async with get_session_factory()() as session:
            athlete = await session.get(Athlete, athlete_id)
            if athlete is None or not athlete.plan_sheet_url:
                return
            await sync_plan(athlete_id, session)
    except Exception:
        logger.warning(
            "plan autosync failed for athlete %s", athlete_id, exc_info=True
        )
