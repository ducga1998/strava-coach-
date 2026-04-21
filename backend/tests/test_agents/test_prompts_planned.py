from app.agents.prompts import SYSTEM_PROMPT, build_debrief_prompt


BASE_ACTIVITY = {
    "activity_name": "morning",
    "duration_sec": 3600,
    "distance_m": 12000,
    "sport_type": "Run",
    "tss": 80,
    "hr_tss": 80,
    "hr_drift_pct": 3.2,
    "aerobic_decoupling_pct": 2.1,
    "ngp_sec_km": 330,
    "zone_distribution": {"z1_pct": 10, "z2_pct": 60, "z3_pct": 20, "z4_pct": 8, "z5_pct": 2},
    "elevation_gain_m": 200,
    "cadence_avg": 175,
}


BASE_CONTEXT = {
    "lthr": 165,
    "threshold_pace_sec_km": 300,
    "tss_30d_avg": 70,
    "acwr": 1.1,
    "ctl": 55,
    "atl": 60,
    "tsb": -5,
    "training_phase": "Build",
    "race_target": None,
    "planned_today": None,
    "planned_tomorrow": None,
}


def test_system_prompt_contains_plan_vs_actual_section():
    assert "PLAN VS ACTUAL" in SYSTEM_PROMPT
    assert "TYPE BREAK" in SYSTEM_PROMPT
    assert "plan_compliance" in SYSTEM_PROMPT or "NN/100" in SYSTEM_PROMPT


def test_build_prompt_omits_plan_section_when_no_plan():
    prompt = build_debrief_prompt(BASE_ACTIVITY, BASE_CONTEXT)
    assert "PLANNED WORKOUT" not in prompt
    assert "PLANNED TOMORROW" not in prompt


def test_build_prompt_includes_plan_section_when_planned_today_present():
    context = {
        **BASE_CONTEXT,
        "planned_today": {
            "date": "2026-04-22",
            "workout_type": "long",
            "planned_tss": 180,
            "planned_duration_min": 240,
            "planned_distance_km": 35,
            "planned_elevation_m": 1200,
            "description": "4h trail Z2",
        },
    }
    prompt = build_debrief_prompt(BASE_ACTIVITY, context)
    assert "PLANNED WORKOUT (today)" in prompt
    assert "Type: long" in prompt
    assert "Planned TSS: 180" in prompt
    assert "4h trail Z2" in prompt


def test_build_prompt_includes_tomorrow_when_present():
    context = {
        **BASE_CONTEXT,
        "planned_tomorrow": {
            "date": "2026-04-23",
            "workout_type": "recovery",
            "planned_tss": 40,
            "planned_duration_min": 45,
            "planned_distance_km": None,
            "planned_elevation_m": None,
            "description": None,
        },
    }
    prompt = build_debrief_prompt(BASE_ACTIVITY, context)
    assert "PLANNED TOMORROW" in prompt
    assert "recovery" in prompt
    assert "45 min" in prompt
