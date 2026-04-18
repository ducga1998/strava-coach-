from typing import Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.activity_ingestion import delete_activity, mark_athlete_deauthorized
from app.workers.tasks import (
    enqueue_activity,
    enqueue_activity_delete,
    enqueue_activity_update,
    enqueue_athlete_revoke,
)

router = APIRouter(prefix="/webhook", tags=["webhook"])


class WebhookEvent(BaseModel):
    object_type: str
    object_id: int
    aspect_type: str
    owner_id: int
    subscription_id: int | None = None
    event_time: int | None = None
    updates: dict[str, Any] = Field(default_factory=dict)


@router.get("/strava")
async def strava_webhook_challenge(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
) -> dict[str, str]:
    if hub_mode != "subscribe":
        raise HTTPException(status_code=403, detail="Invalid hub mode")
    if hub_verify_token != settings.strava_verify_token:
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return {"hub.challenge": hub_challenge}


@router.post("/strava")
async def strava_webhook_event(
    event: WebhookEvent,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if is_activity_upsert(event):
        background_tasks.add_task(enqueue_activity, event.owner_id, event.object_id)
        return {"status": "ok"}
    if is_activity_delete(event):
        await delete_activity(session, event.object_id)
        return {"status": "ok"}
    if is_athlete_deauthorization(event):
        await mark_athlete_deauthorized(session, event.object_id)
    return {"status": "ok"}


def is_activity_upsert(event: WebhookEvent) -> bool:
    return event.object_type == "activity" and event.aspect_type in {"create", "update"}


def is_activity_delete(event: WebhookEvent) -> bool:
    return event.object_type == "activity" and event.aspect_type == "delete"


def is_athlete_deauthorization(event: WebhookEvent) -> bool:
    return (
        event.object_type == "athlete"
        and event.aspect_type == "update"
        and event.updates.get("authorized") in ("false", False)
    )
