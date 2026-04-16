from datetime import datetime

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.activity import Activity
from app.models.metrics import ActivityMetrics

router = APIRouter(prefix="/activities", tags=["activities"])


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
    result = await db.execute(
        select(Activity)
        .where(Activity.athlete_id == athlete_id)
        .order_by(Activity.start_date.desc())
        .limit(50)
    )
    return [activity_list_out(activity) for activity in result.scalars().all()]


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


def activity_list_out(activity: Activity) -> ActivityListOut:
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
    )


def activity_detail_out(activity: Activity) -> ActivityDetailOut:
    listed = activity_list_out(activity)
    return ActivityDetailOut(**listed.model_dump(exclude={"strava_activity_id", "processing_status"}))


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
