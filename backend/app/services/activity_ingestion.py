import logging
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.agents.debrief_graph import generate_debrief
from app.agents.schema import ActivityInput, AthleteContext
from app.metrics.engine import compute_activity_metrics
from app.models.activity import Activity
from app.models.athlete import Athlete, AthleteProfile
from app.models.credentials import StravaCredential
from app.models.metrics import ActivityMetrics
from app.services.strava_client import StravaClientProtocol, StravaStreamPayload
from app.services.strava_client import StravaActivityPayload
from app.services.token_service import TokenService


SUPPORTED_SPORTS = {"Run", "TrailRun", "Hike", "VirtualRun"}


@dataclass(frozen=True)
class IngestionResult:
    status: str
    activity_id: int | None = None
    reason: str | None = None


def is_supported_sport(sport_type: str | None) -> bool:
    return sport_type in SUPPORTED_SPORTS


def should_exclude_from_load(duration_sec: int | None, distance_m: float | None) -> bool:
    return (duration_sec or 0) < 600 or (distance_m or 0.0) < 1000.0


async def ingest_activity(
    session: AsyncSession,
    strava_athlete_id: int,
    strava_activity_id: int,
    client: StravaClientProtocol,
    token_service: TokenService,
) -> IngestionResult:
    athlete = await _find_athlete(session, strava_athlete_id)
    if athlete is None:
        return IngestionResult(status="skipped", reason="athlete_not_found")
    credential = await _find_credential(session, athlete.id)
    if credential is None:
        return IngestionResult(status="skipped", reason="credentials_not_found")
    token = await _get_valid_token(session, credential, client, token_service)
    return await _fetch_store_process(session, athlete.id, strava_activity_id, client, token)


async def backfill_recent_activities(
    session: AsyncSession,
    athlete_id: int,
    client: StravaClientProtocol,
    token_service: TokenService,
    limit: int = 10,
) -> int:
    credential = await _find_credential(session, athlete_id)
    if credential is None:
        return 0
    token = await _get_valid_token(session, credential, client, token_service)
    summaries = await client.get_athlete_activities(token, per_page=limit)
    strava_ids = [s["id"] for s in summaries if "id" in s]
    existing = await _get_existing_strava_ids(session, athlete_id, strava_ids)
    count = 0
    for summary in summaries:
        strava_id = summary.get("id")
        if strava_id is None or strava_id in existing:
            continue
        try:
            await _fetch_store_process(session, athlete_id, strava_id, client, token)
            count += 1
        except Exception:
            logger.warning("backfill skipped activity %s", strava_id, exc_info=True)
    return count


async def _get_existing_strava_ids(
    session: AsyncSession, athlete_id: int, candidate_ids: list[int]
) -> set[int]:
    if not candidate_ids:
        return set()
    result = await session.execute(
        select(Activity.strava_activity_id).where(
            Activity.athlete_id == athlete_id,
            Activity.strava_activity_id.in_(candidate_ids),
        )
    )
    return set(result.scalars().all())


async def _get_valid_token(
    session: AsyncSession,
    credential: StravaCredential,
    client: StravaClientProtocol,
    token_service: TokenService,
) -> str:
    if int(time.time()) < credential.expires_at - 60:
        return token_service.decrypt(credential.access_token_enc)
    refresh_token = token_service.decrypt(credential.refresh_token_enc)
    new_token = await client.refresh_access_token(refresh_token)
    credential.access_token_enc = token_service.encrypt(new_token["access_token"])
    credential.refresh_token_enc = token_service.encrypt(new_token["refresh_token"])
    credential.expires_at = new_token["expires_at"]
    credential.refresh_failure_count = 0
    await session.commit()
    return new_token["access_token"]


async def _fetch_store_process(
    session: AsyncSession,
    athlete_id: int,
    strava_activity_id: int,
    client: StravaClientProtocol,
    access_token: str,
) -> IngestionResult:
    data = await client.get_activity(access_token, strava_activity_id)
    streams = await client.get_activity_streams(access_token, strava_activity_id)
    activity = _build_activity(athlete_id, strava_activity_id, data, streams)
    await _persist_activity(session, activity)
    try:
        await process_activity_metrics(session, activity)
    except Exception:
        activity.processing_status = "failed"
        await session.commit()
        raise
    return IngestionResult(status="stored", activity_id=activity.id)


async def process_activity_metrics(session: AsyncSession, activity: Activity) -> None:
    if not _should_compute_metrics(activity):
        await session.commit()
        return
    profile = await _find_profile(session, activity.athlete_id)
    metrics, values = _compute_metrics(activity, profile)
    session.add(metrics)
    activity.debrief = await _generate_debrief(activity, profile, values)
    activity.processing_status = "done"
    await session.commit()


def _should_compute_metrics(activity: Activity) -> bool:
    if not is_supported_sport(activity.sport_type):
        activity.skipped_reason = "unsupported_sport"
        activity.processing_status = "done"
        return False
    if should_exclude_from_load(activity.elapsed_time_sec, activity.distance_m):
        activity.excluded_from_load = True
        activity.processing_status = "done"
        return False
    return activity.streams_raw is not None


def _compute_metrics(
    activity: Activity, profile: AthleteProfile | None
) -> tuple[ActivityMetrics, dict[str, object]]:
    lthr = profile.lthr if profile and profile.lthr else 155
    threshold_pace = _threshold_pace(profile)
    values = compute_activity_metrics(
        streams=activity.streams_raw or {},
        duration_sec=activity.elapsed_time_sec or 0,
        lthr=lthr,
        threshold_pace_sec_km=threshold_pace,
    )
    return _metrics_model(activity, values), dict(values)


async def _generate_debrief(
    activity: Activity,
    profile: AthleteProfile | None,
    values: dict[str, object],
) -> dict[str, str]:
    activity_input = _activity_input(activity, values)
    context = _athlete_context(profile)
    return await generate_debrief(activity_input, context)


def _activity_input(activity: Activity, values: dict[str, object]) -> ActivityInput:
    return ActivityInput(
        activity_name=activity.name or "Run",
        duration_sec=activity.elapsed_time_sec or 0,
        distance_m=activity.distance_m or 0.0,
        sport_type=activity.sport_type or "Run",
        tss=_float_value(values, "hr_tss"),
        hr_tss=_float_value(values, "hr_tss"),
        hr_drift_pct=_float_value(values, "hr_drift_pct"),
        aerobic_decoupling_pct=_float_value(values, "aerobic_decoupling_pct"),
        ngp_sec_km=_float_value(values, "ngp_sec_km"),
        zone_distribution=_zone_value(values),
    )


def _athlete_context(profile: AthleteProfile | None) -> AthleteContext:
    return AthleteContext(
        lthr=profile.lthr if profile and profile.lthr else 155,
        threshold_pace_sec_km=_threshold_pace(profile),
        tss_30d_avg=60.0,
        acwr=1.0,
        ctl=50.0,
        atl=50.0,
        tsb=0.0,
        training_phase="Build",
    )


def _threshold_pace(profile: AthleteProfile | None) -> int:
    if profile and profile.threshold_pace_sec_km:
        return profile.threshold_pace_sec_km
    return 300


def _metrics_model(
    activity: Activity, values: dict[str, object]
) -> ActivityMetrics:
    return ActivityMetrics(
        activity_id=activity.id,
        athlete_id=activity.athlete_id,
        tss=_float_value(values, "hr_tss"),
        hr_tss=_float_value(values, "hr_tss"),
        gap_avg_sec_km=_float_value(values, "gap_avg_sec_km"),
        ngp_sec_km=_float_value(values, "ngp_sec_km"),
        hr_drift_pct=_float_value(values, "hr_drift_pct"),
        aerobic_decoupling_pct=_float_value(values, "aerobic_decoupling_pct"),
        zone_distribution=_zone_value(values),
    )


def _build_activity(
    athlete_id: int,
    strava_activity_id: int,
    data: StravaActivityPayload,
    streams: StravaStreamPayload,
) -> Activity:
    return Activity(
        athlete_id=athlete_id,
        strava_activity_id=strava_activity_id,
        name=data.get("name"),
        sport_type=data.get("sport_type"),
        start_date=_parse_datetime(data.get("start_date")),
        elapsed_time_sec=data.get("elapsed_time"),
        moving_time_sec=data.get("moving_time"),
        distance_m=data.get("distance"),
        total_elevation_gain_m=data.get("total_elevation_gain"),
        average_heartrate=data.get("average_heartrate"),
        max_heartrate=data.get("max_heartrate"),
        streams_raw=dict(streams),
        processing_status="processing",
    )


async def _persist_activity(session: AsyncSession, activity: Activity) -> None:
    session.add(activity)
    await session.flush()


async def _find_athlete(session: AsyncSession, strava_athlete_id: int) -> Athlete | None:
    result = await session.execute(
        select(Athlete).where(Athlete.strava_athlete_id == strava_athlete_id)
    )
    return result.scalar_one_or_none()


async def _find_credential(
    session: AsyncSession, athlete_id: int
) -> StravaCredential | None:
    result = await session.execute(
        select(StravaCredential).where(StravaCredential.athlete_id == athlete_id)
    )
    return result.scalar_one_or_none()


async def _find_profile(session: AsyncSession, athlete_id: int) -> AthleteProfile | None:
    result = await session.execute(
        select(AthleteProfile).where(AthleteProfile.athlete_id == athlete_id)
    )
    return result.scalar_one_or_none()


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _float_value(values: dict[str, object], key: str) -> float:
    value = values.get(key, 0.0)
    return float(value) if isinstance(value, int | float) else 0.0


def _zone_value(values: dict[str, object]) -> dict[str, float]:
    value = values.get("zone_distribution")
    if not isinstance(value, dict):
        return {}
    return {str(key): float(item) for key, item in value.items() if isinstance(item, int | float)}
