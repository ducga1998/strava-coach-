import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import BigInteger, func, select, type_coerce
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.agents.debrief_graph import generate_debrief
from app.agents.schema import ActivityInput, AthleteContext, RaceTargetContext
from app.config import settings
from app.metrics.engine import compute_activity_metrics
from app.models.activity import Activity
from app.models.athlete import Athlete, AthleteProfile
from app.models.credentials import StravaCredential
from app.models.metrics import ActivityMetrics, LoadHistory
from app.models.target import Priority, RaceTarget
from app.services.description_builder import format_strava_description
from app.services.plan_import import get_planned_for_date, sync_plan
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
    await _push_description(session, activity, client, access_token)
    return IngestionResult(status="stored", activity_id=activity.id)


async def process_activity_metrics(session: AsyncSession, activity: Activity) -> None:
    if not _should_compute_metrics(activity):
        await session.commit()
        return
    profile = await _find_profile(session, activity.athlete_id)
    metrics, values = _compute_metrics(activity, profile)
    await maybe_autosync_plan(session, activity.athlete_id)
    activity_date = activity.start_date.date() if activity.start_date else None
    context = await _build_athlete_context(
        session, activity.athlete_id, profile, activity_date=activity_date
    )
    # Drop any existing metrics row so reprocessing (e.g. admin-triggered
    # regenerate, or a webhook replay) doesn't hit the unique constraint on
    # activity_metrics.activity_id. Flush to guarantee the DELETE reaches the
    # DB before the subsequent INSERT below.
    await _delete_metrics(session, activity.id)
    await session.flush()
    session.add(metrics)
    activity.debrief = await _generate_debrief(activity, context, values)
    activity.processing_status = "done"
    await session.commit()


async def _push_description(
    session: AsyncSession,
    activity: Activity,
    client: StravaClientProtocol,
    access_token: str,
) -> None:
    if not settings.strava_push_description:
        return
    if activity.debrief is None:
        return
    try:
        result = await session.execute(
            select(ActivityMetrics).where(ActivityMetrics.activity_id == activity.id)
        )
        metrics = result.scalar_one_or_none()
        if metrics is None:
            return
        load = await _latest_load(session, activity.athlete_id)
        acwr = load.acwr if load else 1.0
        z2_pct = float((metrics.zone_distribution or {}).get("z2_pct", 0.0))
        feedback_url = (
            f"{settings.frontend_url}/feedback/{activity.id}"
            f"?athlete_id={activity.athlete_id}"
        )
        description = format_strava_description(
            tss=metrics.hr_tss or 0.0,
            acwr=acwr,
            z2_pct=z2_pct,
            hr_drift_pct=metrics.hr_drift_pct or 0.0,
            decoupling_pct=metrics.aerobic_decoupling_pct or 0.0,
            next_action=str(activity.debrief.get("next_session_action", "")),
            deep_dive_url=(
                f"{settings.frontend_url}/activities/{activity.id}"
                f"?athlete_id={activity.athlete_id}"
            ),
            feedback_url=feedback_url,
            nutrition_protocol=str(activity.debrief.get("nutrition_protocol", "")),
            vmm_projection=str(activity.debrief.get("vmm_projection", "")),
        )
        # Our own PUT triggers a Strava update webhook → re-ingestion →
        # recomputed description. If the text is identical to what we last
        # pushed, skip the PUT so we don't kick off another webhook event
        # and burn 2 more reads (plus LLM $) for nothing.
        new_hash = hashlib.sha256(description.encode("utf-8")).hexdigest()
        if activity.description_pushed_hash == new_hash:
            return
        await client.update_activity_description(
            access_token, activity.strava_activity_id, description
        )
        activity.description_pushed_hash = new_hash
    except Exception:
        logger.warning(
            "failed to push description to Strava for activity %s",
            activity.id,
            exc_info=True,
        )


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
    context: AthleteContext,
    values: dict[str, object],
) -> dict[str, str]:
    activity_input = _activity_input(activity, values)
    return await generate_debrief(activity_input, context)


async def maybe_autosync_plan(session: AsyncSession, athlete_id: int) -> None:
    """Trigger a plan sync if the athlete has a sheet configured.

    Failures are logged and swallowed — plan sync must never block
    activity processing.
    """
    athlete = await session.get(Athlete, athlete_id)
    if athlete is None or not athlete.plan_sheet_url:
        return
    try:
        await sync_plan(athlete_id, session)
    except Exception:
        logger.warning(
            "plan autosync failed for athlete %s", athlete_id, exc_info=True
        )


async def _build_athlete_context(
    session: AsyncSession,
    athlete_id: int,
    profile: AthleteProfile | None,
    activity_date: date | None = None,
) -> AthleteContext:
    load = await _latest_load(session, athlete_id)
    tss_avg = await _tss_30d_avg(session, athlete_id)
    target = await _find_nearest_target(session, athlete_id)

    planned_today = None
    planned_tomorrow = None
    if activity_date is not None:
        planned_today = await get_planned_for_date(
            athlete_id, activity_date, session
        )
        planned_tomorrow = await get_planned_for_date(
            athlete_id, activity_date + timedelta(days=1), session
        )

    return AthleteContext(
        lthr=profile.lthr if profile and profile.lthr else 155,
        threshold_pace_sec_km=_threshold_pace(profile),
        tss_30d_avg=tss_avg,
        acwr=load.acwr if load else 1.0,
        ctl=load.ctl if load else 0.0,
        atl=load.atl if load else 0.0,
        tsb=load.tsb if load else 0.0,
        training_phase=_training_phase_for_target(target),
        race_target=_race_target_context(target) if target else None,
        planned_today=planned_today,
        planned_tomorrow=planned_tomorrow,
    )


async def _latest_load(session: AsyncSession, athlete_id: int) -> LoadHistory | None:
    result = await session.execute(
        select(LoadHistory)
        .where(LoadHistory.athlete_id == athlete_id)
        .order_by(LoadHistory.date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _tss_30d_avg(session: AsyncSession, athlete_id: int) -> float:
    cutoff = datetime.combine(date.today() - timedelta(days=30), datetime.min.time())
    result = await session.execute(
        select(func.avg(ActivityMetrics.hr_tss))
        .join(Activity, Activity.id == ActivityMetrics.activity_id)
        .where(
            ActivityMetrics.athlete_id == athlete_id,
            ActivityMetrics.hr_tss.isnot(None),
            Activity.start_date >= cutoff,
        )
    )
    avg = result.scalar_one_or_none()
    return float(avg) if avg else 60.0


async def _find_nearest_target(session: AsyncSession, athlete_id: int) -> RaceTarget | None:
    result = await session.execute(
        select(RaceTarget)
        .where(
            RaceTarget.athlete_id == athlete_id,
            RaceTarget.race_date >= date.today(),
            RaceTarget.priority == Priority.A,
        )
        .order_by(RaceTarget.race_date)
        .limit(1)
    )
    return result.scalar_one_or_none()


def _race_target_context(target: RaceTarget) -> RaceTargetContext:
    weeks_out = max((target.race_date - date.today()).days // 7, 0)
    return RaceTargetContext(
        race_name=target.race_name,
        weeks_out=weeks_out,
        distance_km=target.distance_km,
        goal_time_sec=target.goal_time_sec,
        training_phase=_compute_phase_from_weeks(weeks_out),
    )


def _training_phase_for_target(target: RaceTarget | None) -> str:
    if target is None:
        return "Base"
    weeks_out = (target.race_date - date.today()).days // 7
    return _compute_phase_from_weeks(weeks_out)


def _compute_phase_from_weeks(weeks_out: int) -> str:
    if weeks_out <= 3:
        return "Taper"
    if weeks_out <= 7:
        return "Peak"
    if weeks_out <= 15:
        return "Build"
    return "Base"


def _activity_input(activity: Activity, values: dict[str, object]) -> ActivityInput:
    cadence_data = (activity.streams_raw or {}).get("cadence", {})
    cadence_list = [float(v) for v in (cadence_data.get("data") or []) if isinstance(v, int | float) and v > 0]
    cadence_avg = sum(cadence_list) / len(cadence_list) if cadence_list else None

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
        elevation_gain_m=activity.total_elevation_gain_m or 0.0,
        cadence_avg=cadence_avg,
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
    existing = await _find_activity(session, activity.strava_activity_id)
    if existing is not None:
        await _delete_metrics(session, existing.id)
        _copy_activity_fields(existing, activity)
        await session.flush()
        return
    session.add(activity)
    await session.flush()


async def push_description_for_activity(
    session: AsyncSession,
    activity_id: int,
    client: StravaClientProtocol,
    token_service: TokenService,
) -> str | None:
    result = await session.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if activity is None:
        return None

    if activity.debrief is None and _should_compute_metrics(activity):
        await process_activity_metrics(session, activity)
        await session.refresh(activity)

    if activity.debrief is None:
        return None

    credential = await _find_credential(session, activity.athlete_id)
    if credential is None:
        return None

    token = await _get_valid_token(session, credential, client, token_service)

    metrics_result = await session.execute(
        select(ActivityMetrics).where(ActivityMetrics.activity_id == activity_id)
    )
    metrics = metrics_result.scalar_one_or_none()
    load = await _latest_load(session, activity.athlete_id)
    acwr = load.acwr if load else 1.0
    z2_pct = float((metrics.zone_distribution or {}).get("z2_pct", 0.0)) if metrics else 0.0

    feedback_url = (
        f"{settings.frontend_url}/feedback/{activity.id}"
        f"?athlete_id={activity.athlete_id}"
    )
    description = format_strava_description(
        tss=metrics.hr_tss or 0.0 if metrics else 0.0,
        acwr=acwr,
        z2_pct=z2_pct,
        hr_drift_pct=metrics.hr_drift_pct or 0.0 if metrics else 0.0,
        decoupling_pct=metrics.aerobic_decoupling_pct or 0.0 if metrics else 0.0,
        next_action=str(activity.debrief.get("next_session_action", "")),
        deep_dive_url=(
            f"{settings.frontend_url}/activities/{activity.id}"
            f"?athlete_id={activity.athlete_id}"
        ),
        feedback_url=feedback_url,
        nutrition_protocol=str(activity.debrief.get("nutrition_protocol", "")),
        vmm_projection=str(activity.debrief.get("vmm_projection", "")),
    )
    await client.update_activity_description(token, activity.strava_activity_id, description)
    return description


async def delete_activity(session: AsyncSession, strava_activity_id: int) -> None:
    activity = await _find_activity(session, strava_activity_id)
    if activity is None:
        return
    await session.delete(activity)
    await session.commit()


async def mark_athlete_deauthorized(
    session: AsyncSession, strava_athlete_id: int
) -> None:
    result = await session.execute(
        select(StravaCredential)
        .join(Athlete, Athlete.id == StravaCredential.athlete_id)
        .where(Athlete.strava_athlete_id == strava_athlete_id)
    )
    credential = result.scalar_one_or_none()
    if credential is None:
        return
    credential.source_disconnected = True
    await session.commit()


async def _find_activity(
    session: AsyncSession, strava_activity_id: int
) -> Activity | None:
    result = await session.execute(
        select(Activity).where(
            Activity.strava_activity_id == type_coerce(strava_activity_id, BigInteger)
        )
    )
    return result.scalar_one_or_none()


def _copy_activity_fields(target: Activity, source: Activity) -> None:
    target.athlete_id = source.athlete_id
    target.name = source.name
    target.sport_type = source.sport_type
    target.start_date = source.start_date
    target.elapsed_time_sec = source.elapsed_time_sec
    target.moving_time_sec = source.moving_time_sec
    target.distance_m = source.distance_m
    target.total_elevation_gain_m = source.total_elevation_gain_m
    target.average_heartrate = source.average_heartrate
    target.max_heartrate = source.max_heartrate
    target.streams_raw = source.streams_raw
    if source.processing_status is not None:
        target.processing_status = source.processing_status


async def _delete_metrics(session: AsyncSession, activity_id: int) -> None:
    result = await session.execute(
        select(ActivityMetrics).where(ActivityMetrics.activity_id == activity_id)
    )
    metrics = result.scalar_one_or_none()
    if metrics is not None:
        await session.delete(metrics)


async def _find_athlete(session: AsyncSession, strava_athlete_id: int) -> Athlete | None:
    result = await session.execute(
        select(Athlete).where(
            Athlete.strava_athlete_id == type_coerce(strava_athlete_id, BigInteger)
        )
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
