from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal

from app.database import get_db
from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.feedback import UserFeedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreateRequest(BaseModel):
    activity_id: int = Field(gt=0)
    athlete_id: int = Field(gt=0)
    thumb: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackItemOut(BaseModel):
    id: int
    thumb: Literal["up", "down"]
    comment: str | None
    created_at: datetime


class ExistingFeedbackResponse(BaseModel):
    existing: FeedbackItemOut | None
    strava_activity_id: int


NOT_FOUND = HTTPException(status_code=404, detail="Activity not found")


async def _activity_owned_by(
    db: AsyncSession, activity_id: int, athlete_id: int
) -> Activity:
    athlete = (
        await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    ).scalar_one_or_none()
    if athlete is None:
        raise NOT_FOUND
    activity = (
        await db.execute(
            select(Activity).where(
                Activity.id == activity_id, Activity.athlete_id == athlete_id
            )
        )
    ).scalar_one_or_none()
    if activity is None:
        raise NOT_FOUND
    return activity


@router.post("", response_model=FeedbackItemOut, status_code=201)
async def submit_feedback(
    payload: FeedbackCreateRequest, db: AsyncSession = Depends(get_db)
) -> FeedbackItemOut:
    await _activity_owned_by(db, payload.activity_id, payload.athlete_id)
    row = UserFeedback(
        activity_id=payload.activity_id,
        athlete_id=payload.athlete_id,
        thumb=payload.thumb,
        comment=(payload.comment or "").strip() or None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return FeedbackItemOut(
        id=row.id, thumb=row.thumb, comment=row.comment, created_at=row.created_at  # type: ignore[arg-type]
    )


@router.get("/activity/{activity_id}", response_model=ExistingFeedbackResponse)
async def get_existing_feedback(
    activity_id: int, athlete_id: int, db: AsyncSession = Depends(get_db)
) -> ExistingFeedbackResponse:
    activity = await _activity_owned_by(db, activity_id, athlete_id)
    row = (
        await db.execute(
            select(UserFeedback)
            .where(
                UserFeedback.activity_id == activity_id,
                UserFeedback.athlete_id == athlete_id,
            )
            .order_by(UserFeedback.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    existing = (
        FeedbackItemOut(
            id=row.id, thumb=row.thumb, comment=row.comment, created_at=row.created_at  # type: ignore[arg-type]
        )
        if row is not None
        else None
    )
    return ExistingFeedbackResponse(
        existing=existing, strava_activity_id=activity.strava_activity_id
    )
