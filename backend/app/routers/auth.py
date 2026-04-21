import logging
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import BigInteger, select, type_coerce
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.athlete import Athlete
from app.models.credentials import StravaCredential
from app.services.strava_client import (
    StravaOAuthError,
    StravaPayloadError,
    StravaTokenPayload,
    exchange_code,
    get_authorization_url,
)
from app.services.token_service import TokenServiceError, encrypt
from app.workers.tasks import enqueue_backfill

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
_state_store: set[str] = set()


@router.get("/strava")
async def strava_login() -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    _state_store.add(state)
    return RedirectResponse(get_authorization_url(state))


@router.get("/callback")
async def strava_callback(
    background_tasks: BackgroundTasks,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if state not in _state_store:
        return RedirectResponse(
            f"{settings.frontend_url}/connect?oauth_error=invalid_state", status_code=302
        )
    _state_store.remove(state)

    try:
        token_data = await exchange_code(code)
        athlete = await upsert_athlete(db, token_data)
        await upsert_credentials(db, athlete.id, token_data)
        await db.commit()
    except StravaOAuthError as exc:
        await db.rollback()
        logger.warning("Strava token exchange failed: %s", exc.message)
        return RedirectResponse(
            f"{settings.frontend_url}/connect?oauth_error=strava_token", status_code=302
        )
    except StravaPayloadError as exc:
        await db.rollback()
        logger.warning("Strava token payload invalid: %s", exc)
        return RedirectResponse(
            f"{settings.frontend_url}/connect?oauth_error=strava_payload", status_code=302
        )
    except TokenServiceError:
        await db.rollback()
        logger.exception("Encrypting Strava tokens failed — check ENCRYPTION_KEY")
        return RedirectResponse(
            f"{settings.frontend_url}/connect?oauth_error=encryption_config", status_code=302
        )
    except Exception:
        await db.rollback()
        logger.exception("OAuth callback failed")
        return RedirectResponse(
            f"{settings.frontend_url}/connect?oauth_error=server_error", status_code=302
        )

    # One-time history backfill: only fires when the athlete has never been
    # backfilled. See docs/superpowers/specs/2026-04-21-webhook-only-ingest-design.md.
    if athlete.backfilled_at is None:
        background_tasks.add_task(enqueue_backfill, athlete.id)

    return RedirectResponse(
        f"{settings.frontend_url}/setup?athlete_id={athlete.id}", status_code=302
    )


async def upsert_athlete(
    db: AsyncSession, token_data: StravaTokenPayload
) -> Athlete:
    strava_athlete = token_data["athlete"]
    result = await db.execute(
        select(Athlete).where(
            Athlete.strava_athlete_id == type_coerce(strava_athlete["id"], BigInteger)
        )
    )
    athlete = result.scalar_one_or_none()
    if athlete is not None:
        athlete.firstname = strava_athlete.get("firstname", athlete.firstname)
        athlete.lastname = strava_athlete.get("lastname", athlete.lastname)
        athlete.avatar_url = strava_athlete.get("profile", athlete.avatar_url)
        athlete.city = strava_athlete.get("city", athlete.city)
        athlete.country = strava_athlete.get("country", athlete.country)
        return athlete
    athlete = Athlete(
        strava_athlete_id=strava_athlete["id"],
        firstname=strava_athlete.get("firstname", ""),
        lastname=strava_athlete.get("lastname", ""),
        avatar_url=strava_athlete.get("profile"),
        city=strava_athlete.get("city"),
        country=strava_athlete.get("country"),
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
