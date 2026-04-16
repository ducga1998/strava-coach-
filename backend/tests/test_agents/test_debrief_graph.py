import asyncio

from app.agents.debrief_graph import generate_debrief
from app.agents.schema import ActivityInput, AthleteContext


def test_generate_debrief_structure() -> None:
    result = asyncio.run(generate_debrief(sample_activity(), sample_context()))
    assert set(result) == {
        "load_verdict",
        "technical_insight",
        "next_session_action",
    }
    for field in result.values():
        lowered = field.lower()
        assert "great job" not in lowered
        assert "keep it up" not in lowered
        assert "listen to your body" not in lowered


def sample_activity() -> ActivityInput:
    return ActivityInput(
        activity_name="Morning Trail Run",
        duration_sec=3600,
        distance_m=12000,
        sport_type="TrailRun",
        tss=75.0,
        hr_tss=72.0,
        hr_drift_pct=6.5,
        aerobic_decoupling_pct=4.2,
        ngp_sec_km=310,
        zone_distribution={"z1_pct": 5, "z2_pct": 55, "z3_pct": 30},
    )


def sample_context() -> AthleteContext:
    return AthleteContext(
        lthr=160,
        threshold_pace_sec_km=270,
        tss_30d_avg=60.0,
        acwr=1.1,
        ctl=52.0,
        atl=55.0,
        tsb=-3.0,
        training_phase="Build",
    )
