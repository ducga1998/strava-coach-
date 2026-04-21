from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.training_plan import TrainingPlanEntry
from app.services.plan_import import get_planned_for_date


@pytest_asyncio.fixture
async def athlete(db_session: AsyncSession) -> Athlete:
    athlete = Athlete(strava_athlete_id=1)
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)
    return athlete


@pytest.mark.asyncio
async def test_returns_none_when_no_entry(db_session: AsyncSession, athlete: Athlete):
    result = await get_planned_for_date(athlete.id, date(2026, 4, 22), db_session)
    assert result is None


@pytest.mark.asyncio
async def test_returns_planned_context_when_entry_exists(
    db_session: AsyncSession, athlete: Athlete
):
    db_session.add(
        TrainingPlanEntry(
            athlete_id=athlete.id,
            date=date(2026, 4, 22),
            workout_type="long",
            planned_tss=180,
            planned_duration_min=240,
            planned_distance_km=35,
            planned_elevation_m=1200,
            description="4h trail",
        )
    )
    await db_session.commit()

    result = await get_planned_for_date(athlete.id, date(2026, 4, 22), db_session)
    assert result is not None
    assert result.workout_type == "long"
    assert result.planned_tss == 180
    assert result.description == "4h trail"


@pytest.mark.asyncio
async def test_returns_none_for_other_athletes_entry(
    db_session: AsyncSession, athlete: Athlete
):
    other = Athlete(strava_athlete_id=2)
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    db_session.add(
        TrainingPlanEntry(
            athlete_id=other.id,
            date=date(2026, 4, 22),
            workout_type="easy",
        )
    )
    await db_session.commit()

    result = await get_planned_for_date(athlete.id, date(2026, 4, 22), db_session)
    assert result is None
