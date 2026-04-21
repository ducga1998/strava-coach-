from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.athlete import Athlete
from app.models.training_plan import TrainingPlanEntry
from app.services.plan_import import (
    SyncReport,
    is_valid_sheet_url,
    sync_plan,
)

router = APIRouter(prefix="/plan", tags=["plan"])


class PlanConfigIn(BaseModel):
    athlete_id: int = Field(gt=0)
    sheet_url: str = Field(min_length=1, max_length=500)


class PlanConfigOut(BaseModel):
    athlete_id: int
    sheet_url: str | None
    plan_synced_at: str | None


class PlanSyncIn(BaseModel):
    athlete_id: int = Field(gt=0)


class PlanEntryOut(BaseModel):
    date: date
    workout_type: str
    planned_tss: float | None
    planned_duration_min: int | None
    planned_distance_km: float | None
    planned_elevation_m: int | None
    description: str | None


@router.put("/config", response_model=PlanConfigOut)
async def put_plan_config(
    data: PlanConfigIn, db: AsyncSession = Depends(get_db)
) -> PlanConfigOut:
    if not is_valid_sheet_url(data.sheet_url):
        raise HTTPException(
            status_code=400,
            detail="URL must be a Google Sheets published CSV link "
            "(https://docs.google.com/spreadsheets/.../pub?output=csv)",
        )
    athlete = await db.get(Athlete, data.athlete_id)
    if athlete is None:
        raise HTTPException(status_code=404, detail="athlete not found")
    athlete.plan_sheet_url = data.sheet_url
    await db.commit()
    await db.refresh(athlete)
    return PlanConfigOut(
        athlete_id=athlete.id,
        sheet_url=athlete.plan_sheet_url,
        plan_synced_at=athlete.plan_synced_at.isoformat()
        if athlete.plan_synced_at
        else None,
    )


@router.delete("/config", status_code=204)
async def delete_plan_config(
    athlete_id: int, db: AsyncSession = Depends(get_db)
) -> Response:
    athlete = await db.get(Athlete, athlete_id)
    if athlete is None:
        raise HTTPException(status_code=404, detail="athlete not found")
    athlete.plan_sheet_url = None
    athlete.plan_synced_at = None
    await db.commit()
    return Response(status_code=204)


@router.post("/sync", response_model=SyncReport)
async def post_plan_sync(
    data: PlanSyncIn, db: AsyncSession = Depends(get_db)
) -> SyncReport:
    return await sync_plan(data.athlete_id, db)


@router.get("", response_model=list[PlanEntryOut])
async def get_plan_range(
    athlete_id: int,
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    db: AsyncSession = Depends(get_db),
) -> list[PlanEntryOut]:
    result = await db.execute(
        select(TrainingPlanEntry)
        .where(
            TrainingPlanEntry.athlete_id == athlete_id,
            TrainingPlanEntry.date >= from_,
            TrainingPlanEntry.date <= to,
        )
        .order_by(TrainingPlanEntry.date)
    )
    rows = result.scalars().all()
    return [
        PlanEntryOut(
            date=row.date,
            workout_type=row.workout_type,
            planned_tss=row.planned_tss,
            planned_duration_min=row.planned_duration_min,
            planned_distance_km=row.planned_distance_km,
            planned_elevation_m=row.planned_elevation_m,
            description=row.description,
        )
        for row in rows
    ]
