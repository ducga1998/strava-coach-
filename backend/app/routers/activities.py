from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.activity import Activity
from app.models.metrics import ActivityMetrics
from app.services.activity_ingestion import push_description_for_activity
from app.services.strava_client import StravaClient
from app.services.token_service import get_token_service

router = APIRouter(prefix="/activities", tags=["activities"])

EffortLabel = Literal["easy", "tempo", "hard"]


class ActivityListOut(BaseModel):
    id: int
    strava_activity_id: int
    name: str
    sport_type: str
    start_date: datetime | None
    distance_m: float
    elapsed_time_sec: int
    total_elevation_gain_m: float | None
    processing_status: str
    hr_tss: float | None = None
    effort: EffortLabel | None = None


class MetricsOut(BaseModel):
    tss: float | None
    hr_tss: float | None
    gap_avg_sec_km: float | None
    ngp_sec_km: float | None
    hr_drift_pct: float | None
    aerobic_decoupling_pct: float | None
    zone_distribution: dict[str, float] | None


class DebriefOut(BaseModel):
    load_verdict: str
    technical_insight: str
    next_session_action: str
    nutrition_protocol: str = ""
    vmm_projection: str = ""


class ActivityDetailOut(BaseModel):
    id: int
    name: str
    sport_type: str
    start_date: datetime | None
    distance_m: float
    elapsed_time_sec: int
    total_elevation_gain_m: float | None


class ActivityResponse(BaseModel):
    activity: ActivityDetailOut
    metrics: MetricsOut | None
    debrief: DebriefOut | None


@router.get("/", response_model=list[ActivityListOut])
async def list_activities(
    athlete_id: int, db: AsyncSession = Depends(get_db)
) -> list[ActivityListOut]:
    stmt = (
        select(Activity, ActivityMetrics)
        .outerjoin(ActivityMetrics, ActivityMetrics.activity_id == Activity.id)
        .where(Activity.athlete_id == athlete_id)
        .order_by(Activity.start_date.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    return [activity_list_out(activity, metrics) for activity, metrics in result.all()]


@router.post("/{activity_id}/push-description")
async def push_description(
    activity_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    description = await push_description_for_activity(
        session=db,
        activity_id=activity_id,
        client=StravaClient(),
        token_service=get_token_service(),
    )
    if description is None:
        raise HTTPException(status_code=422, detail="Cannot generate description: activity has no metrics or debrief")
    return {"description": description}


@router.get("/{activity_id}", response_model=ActivityResponse)
async def get_activity_detail(
    activity_id: int, db: AsyncSession = Depends(get_db)
) -> ActivityResponse:
    activity = await find_activity(db, activity_id)
    metrics = await find_metrics(db, activity_id)
    return ActivityResponse(
        activity=activity_detail_out(activity),
        metrics=metrics_out(metrics),
        debrief=debrief_out(activity.debrief),
    )


async def find_activity(db: AsyncSession, activity_id: int) -> Activity:
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


async def find_metrics(
    db: AsyncSession, activity_id: int
) -> ActivityMetrics | None:
    result = await db.execute(
        select(ActivityMetrics).where(ActivityMetrics.activity_id == activity_id)
    )
    return result.scalar_one_or_none()


def activity_list_out(
    activity: Activity, metrics: ActivityMetrics | None = None
) -> ActivityListOut:
    return ActivityListOut(
        id=activity.id,
        strava_activity_id=activity.strava_activity_id,
        name=activity.name or "Untitled activity",
        sport_type=activity.sport_type or "Run",
        start_date=activity.start_date,
        distance_m=activity.distance_m or 0.0,
        elapsed_time_sec=activity.elapsed_time_sec or 0,
        total_elevation_gain_m=activity.total_elevation_gain_m,
        processing_status=activity.processing_status,
        hr_tss=metrics.hr_tss if metrics else None,
        effort=classify_effort(metrics.zone_distribution) if metrics else None,
    )


def activity_detail_out(activity: Activity) -> ActivityDetailOut:
    listed = activity_list_out(activity)
    return ActivityDetailOut(
        **listed.model_dump(
            exclude={"strava_activity_id", "processing_status", "hr_tss", "effort"}
        )
    )


def classify_effort(
    zones: dict[str, float] | None,
) -> EffortLabel | None:
    """Classify session intensity from zone distribution.

    ≥20% in Z4+Z5 → hard; ≥20% in Z3 → tempo; else → easy.
    Returns None when zone data is missing so the UI can hide the badge.
    """
    if not zones:
        return None
    hard = zones.get("z4_pct", 0.0) + zones.get("z5_pct", 0.0)
    if hard >= 20.0:
        return "hard"
    if zones.get("z3_pct", 0.0) >= 20.0:
        return "tempo"
    return "easy"


def metrics_out(metrics: ActivityMetrics | None) -> MetricsOut | None:
    if metrics is None:
        return None
    return MetricsOut(
        tss=metrics.tss,
        hr_tss=metrics.hr_tss,
        gap_avg_sec_km=metrics.gap_avg_sec_km,
        ngp_sec_km=metrics.ngp_sec_km,
        hr_drift_pct=metrics.hr_drift_pct,
        aerobic_decoupling_pct=metrics.aerobic_decoupling_pct,
        zone_distribution=metrics.zone_distribution,
    )


def debrief_out(value: dict[str, object] | None) -> DebriefOut | None:
    if value is None:
        return None
    return DebriefOut.model_validate(value)
