from datetime import date, timedelta

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.metrics import LoadHistory
from app.models.target import Priority, RaceTarget

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class LoadPointOut(BaseModel):
    date: date
    ctl: float
    atl: float
    tsb: float
    acwr: float


class LoadSnapshotOut(BaseModel):
    ctl: float
    atl: float
    tsb: float
    acwr: float


class WeeklyVolumeOut(BaseModel):
    distance_km: float
    elevation_gain_m: float


class TargetSummaryOut(BaseModel):
    id: int
    race_name: str
    race_date: date
    distance_km: float
    elevation_gain_m: float | None
    goal_time_sec: int | None
    priority: Priority


class DashboardLoadOut(BaseModel):
    training_phase: str
    latest: LoadSnapshotOut
    history: list[LoadPointOut]
    weekly_volume: WeeklyVolumeOut
    target: TargetSummaryOut | None


@router.get("/load", response_model=DashboardLoadOut)
async def get_load(
    athlete_id: int,
    db: AsyncSession = Depends(get_db),
) -> DashboardLoadOut:
    history = await load_history(db, athlete_id)
    target = await nearest_a_target(db, athlete_id)
    return DashboardLoadOut(
        training_phase=compute_phase(target.race_date) if target else "Base",
        latest=latest_snapshot(history),
        history=[load_point(row) for row in history],
        weekly_volume=WeeklyVolumeOut(distance_km=0.0, elevation_gain_m=0.0),
        target=target_summary(target),
    )


async def load_history(db: AsyncSession, athlete_id: int) -> list[LoadHistory]:
    cutoff = date.today() - timedelta(days=90)
    result = await db.execute(
        select(LoadHistory)
        .where(LoadHistory.athlete_id == athlete_id, LoadHistory.date >= cutoff)
        .order_by(LoadHistory.date)
    )
    return list(result.scalars().all())


async def nearest_a_target(
    db: AsyncSession, athlete_id: int
) -> RaceTarget | None:
    result = await db.execute(
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


def compute_phase(race_date: date) -> str:
    weeks_out = (race_date - date.today()).days // 7
    if weeks_out <= 3:
        return "Taper"
    if weeks_out <= 7:
        return "Peak"
    if weeks_out <= 15:
        return "Build"
    return "Base"


def latest_snapshot(history: list[LoadHistory]) -> LoadSnapshotOut:
    latest = history[-1] if history else None
    return LoadSnapshotOut(
        ctl=latest.ctl if latest else 0.0,
        atl=latest.atl if latest else 0.0,
        tsb=latest.tsb if latest else 0.0,
        acwr=latest.acwr if latest else 1.0,
    )


def load_point(row: LoadHistory) -> LoadPointOut:
    return LoadPointOut(
        date=row.date,
        ctl=row.ctl,
        atl=row.atl,
        tsb=row.tsb,
        acwr=row.acwr,
    )


def target_summary(target: RaceTarget | None) -> TargetSummaryOut | None:
    if target is None:
        return None
    return TargetSummaryOut(
        id=target.id,
        race_name=target.race_name,
        race_date=target.race_date,
        distance_km=target.distance_km,
        elevation_gain_m=target.elevation_gain_m,
        goal_time_sec=target.goal_time_sec,
        priority=target.priority,
    )
