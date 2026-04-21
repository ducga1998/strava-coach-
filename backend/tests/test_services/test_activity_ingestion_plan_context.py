from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.athlete import Athlete, AthleteProfile
from app.models.training_plan import TrainingPlanEntry
from app.services.activity_ingestion import _build_athlete_context


@pytest.mark.asyncio
async def test_build_context_includes_planned_today_and_tomorrow(
    db_session: AsyncSession,
):
    athlete = Athlete(strava_athlete_id=1)
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)

    activity_date = date(2026, 4, 22)
    db_session.add_all(
        [
            TrainingPlanEntry(
                athlete_id=athlete.id,
                date=activity_date,
                workout_type="long",
                planned_tss=180,
            ),
            TrainingPlanEntry(
                athlete_id=athlete.id,
                date=date(2026, 4, 23),
                workout_type="recovery",
                planned_tss=40,
            ),
        ]
    )
    await db_session.commit()

    context = await _build_athlete_context(
        db_session, athlete.id, profile=None, activity_date=activity_date
    )

    assert context.planned_today is not None
    assert context.planned_today.workout_type == "long"
    assert context.planned_tomorrow is not None
    assert context.planned_tomorrow.workout_type == "recovery"


@pytest.mark.asyncio
async def test_build_context_planned_none_when_no_entries(
    db_session: AsyncSession,
):
    athlete = Athlete(strava_athlete_id=1)
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)

    context = await _build_athlete_context(
        db_session, athlete.id, profile=None, activity_date=date(2026, 4, 22)
    )
    assert context.planned_today is None
    assert context.planned_tomorrow is None
