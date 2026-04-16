from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.athlete import AthleteProfile, Units

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class ProfileIn(BaseModel):
    athlete_id: int = Field(gt=0)
    lthr: int | None = Field(default=None, gt=0)
    max_hr: int | None = Field(default=None, gt=0)
    threshold_pace_sec_km: int | None = Field(default=None, gt=0)
    weight_kg: float | None = Field(default=None, gt=0)
    vo2max_estimate: float | None = Field(default=None, gt=0)
    units: Units = Units.metric
    language: str = Field(default="en", min_length=2, max_length=10)


class ProfileOut(BaseModel):
    athlete_id: int
    onboarding_complete: bool


@router.post("/profile", response_model=ProfileOut)
async def save_profile(
    data: ProfileIn, db: AsyncSession = Depends(get_db)
) -> ProfileOut:
    profile = await find_profile(db, data.athlete_id)
    if profile is None:
        profile = AthleteProfile(athlete_id=data.athlete_id)
        db.add(profile)
    apply_profile(profile, data)
    await db.commit()
    return ProfileOut(athlete_id=data.athlete_id, onboarding_complete=True)


async def find_profile(
    db: AsyncSession, athlete_id: int
) -> AthleteProfile | None:
    result = await db.execute(
        select(AthleteProfile).where(AthleteProfile.athlete_id == athlete_id)
    )
    return result.scalar_one_or_none()


def apply_profile(profile: AthleteProfile, data: ProfileIn) -> None:
    for field in editable_profile_fields():
        value = getattr(data, field)
        if value is not None:
            setattr(profile, field, value)
    profile.onboarding_complete = True


def editable_profile_fields() -> tuple[str, ...]:
    return (
        "lthr",
        "max_hr",
        "threshold_pace_sec_km",
        "weight_kg",
        "vo2max_estimate",
        "units",
        "language",
    )
