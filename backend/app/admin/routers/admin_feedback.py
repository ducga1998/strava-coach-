from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal

from app.admin import auth as admin_auth
from app.admin.models import Admin
from app.database import get_db
from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.feedback import UserFeedback

router = APIRouter(prefix="/admin/feedback", tags=["admin-feedback"])

PAGE_SIZE = 20


class AdminFeedbackItem(BaseModel):
    id: int
    thumb: Literal["up", "down"]
    comment: str | None
    created_at: datetime
    read_at: datetime | None
    activity_id: int
    activity_name: str
    athlete_id: int
    athlete_name: str


class AdminFeedbackPage(BaseModel):
    items: list[AdminFeedbackItem]
    next_cursor: int | None


class AdminFeedbackCounts(BaseModel):
    all: int
    up: int
    down: int
    unread: int


def _athlete_display_name(athlete: Athlete) -> str:
    parts = [p for p in (athlete.firstname, athlete.lastname) if p]
    if parts:
        return " ".join(parts).strip()
    return f"athlete-{athlete.id}"


@router.get("", response_model=AdminFeedbackPage)
async def list_feedback(
    thumb: Literal["up", "down"] | None = None,
    unread: bool = False,
    cursor: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(admin_auth.require_admin),
) -> AdminFeedbackPage:
    stmt = (
        select(UserFeedback, Activity, Athlete)
        .join(Activity, Activity.id == UserFeedback.activity_id)
        .join(Athlete, Athlete.id == UserFeedback.athlete_id)
        .order_by(UserFeedback.id.desc())
        .limit(PAGE_SIZE)
    )
    if thumb is not None:
        stmt = stmt.where(UserFeedback.thumb == thumb)
    if unread:
        stmt = stmt.where(UserFeedback.read_at.is_(None))
    if cursor is not None:
        stmt = stmt.where(UserFeedback.id < cursor)

    rows = (await db.execute(stmt)).all()
    items = [
        AdminFeedbackItem(
            id=fb.id,
            thumb=fb.thumb,  # type: ignore[arg-type]
            comment=fb.comment,
            created_at=fb.created_at,
            read_at=fb.read_at,
            activity_id=activity.id,
            activity_name=activity.name or "Untitled activity",
            athlete_id=athlete.id,
            athlete_name=_athlete_display_name(athlete),
        )
        for fb, activity, athlete in rows
    ]
    next_cursor = items[-1].id if len(items) == PAGE_SIZE else None
    return AdminFeedbackPage(items=items, next_cursor=next_cursor)


@router.get("/counts", response_model=AdminFeedbackCounts)
async def feedback_counts(
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(admin_auth.require_admin),
) -> AdminFeedbackCounts:
    stmt = select(
        func.count(UserFeedback.id),
        func.count(case((UserFeedback.thumb == "up", 1))),
        func.count(case((UserFeedback.thumb == "down", 1))),
        func.count(case((UserFeedback.read_at.is_(None), 1))),
    )
    row = (await db.execute(stmt)).one()
    return AdminFeedbackCounts(all=row[0], up=row[1], down=row[2], unread=row[3])


@router.patch("/{feedback_id}/read", status_code=204)
async def mark_feedback_read(
    feedback_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(admin_auth.require_admin),
) -> Response:
    row = await db.get(UserFeedback, feedback_id)
    if row is not None and row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        await db.commit()
    return Response(status_code=204)
