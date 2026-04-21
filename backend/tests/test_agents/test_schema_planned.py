from datetime import date

from app.agents.schema import AthleteContext, PlannedWorkoutContext


def test_planned_workout_context_requires_date_and_type():
    planned = PlannedWorkoutContext(date=date(2026, 4, 22), workout_type="long")
    assert planned.date == date(2026, 4, 22)
    assert planned.workout_type == "long"
    assert planned.planned_tss is None


def test_athlete_context_defaults_planned_to_none():
    context = AthleteContext(
        lthr=155,
        threshold_pace_sec_km=300,
        tss_30d_avg=50,
        acwr=1.0,
        ctl=60,
        atl=55,
        tsb=5,
        training_phase="Build",
    )
    assert context.planned_today is None
    assert context.planned_tomorrow is None


def test_athlete_context_accepts_planned_workouts():
    planned = PlannedWorkoutContext(date=date(2026, 4, 22), workout_type="long")
    context = AthleteContext(
        lthr=155,
        threshold_pace_sec_km=300,
        tss_30d_avg=50,
        acwr=1.0,
        ctl=60,
        atl=55,
        tsb=5,
        training_phase="Build",
        planned_today=planned,
    )
    assert context.planned_today is not None
    assert context.planned_today.workout_type == "long"
