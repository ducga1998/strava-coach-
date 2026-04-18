from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.athlete import Athlete, AthleteProfile

router = APIRouter(prefix="/athletes", tags=["athletes"])


class AthleteProfileOut(BaseModel):
    onboarding_complete: bool
    lthr: int | None
    max_hr: int | None
    threshold_pace_sec_km: int | None
    weight_kg: float | None
    vo2max_estimate: float | None


class AthleteOut(BaseModel):
    id: int
    strava_athlete_id: int
    firstname: str | None
    lastname: str | None
    avatar_url: str | None
    city: str | None
    country: str | None
    profile: AthleteProfileOut | None


@router.get("/{athlete_id}", response_model=AthleteOut)
async def get_athlete(
    athlete_id: int, db: AsyncSession = Depends(get_db)
) -> AthleteOut:
    result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = result.scalar_one_or_none()
    if athlete is None:
        raise HTTPException(status_code=404, detail="Athlete not found")
    profile = await _find_profile(db, athlete_id)
    return AthleteOut(
        id=athlete.id,
        strava_athlete_id=athlete.strava_athlete_id,
        firstname=athlete.firstname,
        lastname=athlete.lastname,
        avatar_url=athlete.avatar_url,
        city=athlete.city,
        country=athlete.country,
        profile=_profile_out(profile),
    )


async def _find_profile(db: AsyncSession, athlete_id: int) -> AthleteProfile | None:
    result = await db.execute(
        select(AthleteProfile).where(AthleteProfile.athlete_id == athlete_id)
    )
    return result.scalar_one_or_none()


def _profile_out(profile: AthleteProfile | None) -> AthleteProfileOut | None:
    if profile is None:
        return None
    return AthleteProfileOut(
        onboarding_complete=profile.onboarding_complete,
        lthr=profile.lthr,
        max_hr=profile.max_hr,
        threshold_pace_sec_km=profile.threshold_pace_sec_km,
        weight_kg=profile.weight_kg,
        vo2max_estimate=profile.vo2max_estimate,
    )
