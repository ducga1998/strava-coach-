from pydantic import BaseModel, Field
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.config import settings
from app.workers.tasks import enqueue_activity

router = APIRouter(prefix="/webhook", tags=["webhook"])


class WebhookEvent(BaseModel):
    object_type: str
    object_id: int
    aspect_type: str
    owner_id: int
    subscription_id: int | None = None
    event_time: int | None = None
    updates: dict[str, str] = Field(default_factory=dict)


@router.get("/strava")
async def strava_webhook_challenge(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
) -> dict[str, str]:
    if hub_verify_token != settings.strava_verify_token:
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return {"hub.challenge": hub_challenge}


@router.post("/strava")
async def strava_webhook_event(
    event: WebhookEvent, background_tasks: BackgroundTasks
) -> dict[str, str]:
    if should_enqueue(event):
        background_tasks.add_task(enqueue_activity, event.owner_id, event.object_id)
    return {"status": "ok"}


def should_enqueue(event: WebhookEvent) -> bool:
    return event.object_type == "activity" and event.aspect_type == "create"
