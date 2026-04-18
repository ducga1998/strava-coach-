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


from app.agents.schema import RaceTargetContext
from app.agents.debrief_graph import next_session_action, _is_ultra_target


def test_next_session_action_no_target_recovery() -> None:
    result = next_session_action(acwr=1.6, tsb=-35.0, target=None)
    assert "Recovery" in result
    assert "Z1" in result or "Z1-Z2" in result


def test_next_session_action_no_target_underload() -> None:
    result = next_session_action(acwr=0.7, tsb=5.0, target=None)
    assert "Z2" in result
    assert "strides" in result.lower() or "aerobic" in result.lower()


def test_next_session_action_prepends_race_name() -> None:
    target = RaceTargetContext(
        race_name="UTMB", weeks_out=10, distance_km=171.0, training_phase="Build"
    )
    result = next_session_action(acwr=1.1, tsb=-5.0, target=target)
    assert result.startswith("UTMB 10w:")


def test_next_session_action_vmm_ultra_build_adds_descent_cue() -> None:
    target = RaceTargetContext(
        race_name="VMM", weeks_out=8, distance_km=160.0, training_phase="Build"
    )
    result = next_session_action(acwr=1.1, tsb=2.0, target=target)
    assert "VMM 8w:" in result
    assert "downhill" in result.lower() or "descent" in result.lower() or ">15%" in result


def test_next_session_action_vmm_no_descent_when_fatigued() -> None:
    target = RaceTargetContext(
        race_name="VMM", weeks_out=8, distance_km=160.0, training_phase="Build"
    )
    result = next_session_action(acwr=1.6, tsb=-35.0, target=target)
    assert "VMM 8w:" in result
    assert "Recovery" in result


def test_is_ultra_target_by_distance() -> None:
    target = RaceTargetContext(
        race_name="Some Race", weeks_out=10, distance_km=100.0, training_phase="Build"
    )
    assert _is_ultra_target(target) is True


def test_is_ultra_target_by_name() -> None:
    target = RaceTargetContext(
        race_name="VMM 80km", weeks_out=10, distance_km=50.0, training_phase="Build"
    )
    assert _is_ultra_target(target) is True


def test_is_ultra_target_false_for_marathon() -> None:
    target = RaceTargetContext(
        race_name="Paris Marathon", weeks_out=10, distance_km=42.2, training_phase="Build"
    )
    assert _is_ultra_target(target) is False
