import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.athlete import Athlete
from app.models.credentials import StravaCredential
from app.services.strava_client import exchange_code, get_authorization_url
from app.services.strava_client import StravaTokenPayload
from app.services.token_service import encrypt

router = APIRouter(prefix="/auth", tags=["auth"])
_state_store: set[str] = set()


@router.get("/strava")
async def strava_login() -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    _state_store.add(state)
    return RedirectResponse(get_authorization_url(state))


@router.get("/callback")
async def strava_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    validate_state(state)
    token_data = await exchange_code(code)
    athlete = await upsert_athlete(db, token_data)
    await upsert_credentials(db, athlete.id, token_data)
    await db.commit()
    return RedirectResponse(f"{settings.frontend_url}/setup?athlete_id={athlete.id}")


def validate_state(state: str) -> None:
    if state not in _state_store:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    _state_store.remove(state)


async def upsert_athlete(
    db: AsyncSession, token_data: StravaTokenPayload
) -> Athlete:
    strava_athlete = token_data["athlete"]
    result = await db.execute(
        select(Athlete).where(Athlete.strava_athlete_id == strava_athlete["id"])
    )
    athlete = result.scalar_one_or_none()
    if athlete is not None:
        return athlete
    athlete = Athlete(
        strava_athlete_id=strava_athlete["id"],
        firstname=strava_athlete.get("firstname", ""),
        lastname=strava_athlete.get("lastname", ""),
    )
    db.add(athlete)
    await db.flush()
    return athlete


async def upsert_credentials(
    db: AsyncSession, athlete_id: int, token_data: StravaTokenPayload
) -> None:
    result = await db.execute(
        select(StravaCredential).where(StravaCredential.athlete_id == athlete_id)
    )
    credential = result.scalar_one_or_none() or StravaCredential(athlete_id=athlete_id)
    credential.access_token_enc = encrypt(token_data["access_token"])
    credential.refresh_token_enc = encrypt(token_data["refresh_token"])
    credential.expires_at = token_data["expires_at"]
    credential.source_disconnected = False
    db.add(credential)
