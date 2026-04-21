from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schema import ActivityInput, AthleteContext
from app.agents.debrief_graph import fallback_debrief
from app.models.activity import Activity
from app.models.athlete import Athlete, AthleteProfile
from app.services.activity_ingestion import _build_athlete_context
from app.services.plan_import import sync_plan


CSV_BODY = """date,workout_type,planned_tss,planned_duration_min,planned_distance_km,planned_elevation_m,description
2026-04-22,easy,50,45,7,50,"HR cap LTHR-20, flat only"
2026-04-23,long,180,240,35,1200,"4h trail Z2"
"""


@pytest.mark.asyncio
async def test_sync_enrich_fallback_produces_compliance(
    db_session: AsyncSession, monkeypatch
):
    athlete = Athlete(
        strava_athlete_id=1,
        plan_sheet_url="https://docs.google.com/spreadsheets/d/x/pub?output=csv",
    )
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)

    async def fake_fetch(_url: str) -> str:
        return CSV_BODY

    monkeypatch.setattr("app.services.plan_import.fetch_plan_sheet", fake_fetch)

    # In production, plan autosync runs on an isolated session via
    # workers.tasks.enqueue_plan_sync. For this integration test we call
    # sync_plan directly on the test session — equivalent DB effect, same
    # end-to-end path from CSV body → parsed entries → context enrichment.
    await sync_plan(athlete.id, db_session)

    # Build context as if processing an activity on 2026-04-22
    context = await _build_athlete_context(
        db_session, athlete.id, profile=None, activity_date=date(2026, 4, 22)
    )
    assert context.planned_today is not None
    assert context.planned_today.workout_type == "easy"
    assert context.planned_tomorrow is not None
    assert context.planned_tomorrow.workout_type == "long"

    # Simulate an overcooked easy day: planned easy 50 TSS, actual long Z3-Z4
    activity = ActivityInput(
        activity_name="overcooked easy",
        duration_sec=90 * 60,
        distance_m=13000,
        sport_type="Run",
        tss=140,
        hr_tss=140,
        hr_drift_pct=7,
        aerobic_decoupling_pct=6,
        ngp_sec_km=330,
        zone_distribution={"z1_pct": 5, "z2_pct": 30, "z3_pct": 40, "z4_pct": 20, "z5_pct": 5},
        elevation_gain_m=200,
        cadence_avg=175,
    )

    debrief = fallback_debrief(activity, context)
    assert debrief.plan_compliance != ""
    assert debrief.plan_compliance.startswith(
        tuple(f"{i}/100 " for i in range(0, 101))
    )
    # Two axes failed (TSS +180%, TYPE BREAK on easy) → low score
    score = int(debrief.plan_compliance.split("/", 1)[0])
    assert score < 50


@pytest.mark.asyncio
async def test_no_plan_yields_empty_compliance(db_session: AsyncSession):
    athlete = Athlete(strava_athlete_id=1)
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)

    context = await _build_athlete_context(
        db_session, athlete.id, profile=None, activity_date=date(2026, 4, 22)
    )
    assert context.planned_today is None

    activity = ActivityInput(
        activity_name="normal",
        duration_sec=3600,
        distance_m=10000,
        sport_type="Run",
        tss=60,
        hr_tss=60,
        hr_drift_pct=3,
        aerobic_decoupling_pct=2,
        ngp_sec_km=360,
        zone_distribution={"z1_pct": 10, "z2_pct": 70, "z3_pct": 15, "z4_pct": 5, "z5_pct": 0},
        elevation_gain_m=100,
    )
    debrief = fallback_debrief(activity, context)
    assert debrief.plan_compliance == ""
