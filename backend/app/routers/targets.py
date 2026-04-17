from datetime import date

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.target import Priority, RaceTarget

router = APIRouter(prefix="/targets", tags=["targets"])


class TargetIn(BaseModel):
    athlete_id: int = Field(gt=0)
    race_name: str = Field(min_length=1, max_length=255)
    race_date: date
    distance_km: float | None = Field(default=None, gt=0)
    elevation_gain_m: float | None = Field(default=None, ge=0)
    goal_time_sec: int | None = Field(default=None, gt=0)
    priority: Priority = Priority.A


class TargetUpdateIn(BaseModel):
    athlete_id: int = Field(gt=0)
    race_name: str | None = Field(default=None, min_length=1, max_length=255)
    race_date: date | None = None
    distance_km: float | None = Field(default=None, gt=0)
    elevation_gain_m: float | None = Field(default=None, ge=0)
    goal_time_sec: int | None = Field(default=None, gt=0)
    priority: Priority | None = None


class TargetOut(BaseModel):
    id: int
    athlete_id: int
    race_name: str
    race_date: date
    distance_km: float
    elevation_gain_m: float | None
    goal_time_sec: int | None
    priority: Priority


@router.post("", response_model=TargetOut, status_code=201)
@router.post("/", response_model=TargetOut, status_code=201)
async def create_target(
    data: TargetIn, db: AsyncSession = Depends(get_db)
) -> TargetOut:
    target = RaceTarget(
        athlete_id=data.athlete_id,
        race_name=data.race_name,
        race_date=data.race_date,
        distance_km=known_distance_km(data.distance_km),
        elevation_gain_m=data.elevation_gain_m,
        goal_time_sec=data.goal_time_sec,
        priority=data.priority,
    )
    db.add(target)
    await db.commit()
    await db.refresh(target)
    return target_out(target)


@router.get("", response_model=list[TargetOut])
@router.get("/", response_model=list[TargetOut])
async def list_targets(
    athlete_id: int, db: AsyncSession = Depends(get_db)
) -> list[TargetOut]:
    result = await db.execute(targets_query(athlete_id))
    return [target_out(target) for target in result.scalars().all()]


@router.put("/{target_id}", response_model=TargetOut)
async def update_target(
    target_id: int, data: TargetUpdateIn, db: AsyncSession = Depends(get_db)
) -> TargetOut:
    target = await get_target_or_404(db, target_id, data.athlete_id)
    apply_target_update(target, data)
    await db.commit()
    await db.refresh(target)
    return target_out(target)


@router.delete("/{target_id}", status_code=204)
async def delete_target(
    target_id: int, athlete_id: int, db: AsyncSession = Depends(get_db)
) -> Response:
    target = await get_target_or_404(db, target_id, athlete_id)
    await db.delete(target)
    await db.commit()
    return Response(status_code=204)


def targets_query(athlete_id: int):
    return (
        select(RaceTarget)
        .where(RaceTarget.athlete_id == athlete_id)
        .order_by(RaceTarget.race_date)
    )


async def get_target_or_404(
    db: AsyncSession, target_id: int, athlete_id: int
) -> RaceTarget:
    result = await db.execute(
        select(RaceTarget).where(
            RaceTarget.id == target_id,
            RaceTarget.athlete_id == athlete_id,
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Target not found")
    return target


def apply_target_update(target: RaceTarget, data: TargetUpdateIn) -> None:
    if data.race_name is not None:
        target.race_name = data.race_name
    if data.race_date is not None:
        target.race_date = data.race_date
    if "distance_km" in data.model_fields_set:
        target.distance_km = known_distance_km(data.distance_km)
    if "elevation_gain_m" in data.model_fields_set:
        target.elevation_gain_m = data.elevation_gain_m
    if "goal_time_sec" in data.model_fields_set:
        target.goal_time_sec = data.goal_time_sec
    if data.priority is not None:
        target.priority = data.priority


def known_distance_km(distance_km: float | None) -> float:
    if distance_km is None:
        return 0.0
    return distance_km


def target_out(target: RaceTarget) -> TargetOut:
    return TargetOut(
        id=target.id,
        athlete_id=target.athlete_id,
        race_name=target.race_name,
        race_date=target.race_date,
        distance_km=target.distance_km,
        elevation_gain_m=target.elevation_gain_m,
        goal_time_sec=target.goal_time_sec,
        priority=target.priority,
    )
