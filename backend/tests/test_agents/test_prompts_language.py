"""Language toggle affects the debrief prompt — instruction block appears only for vi."""
from app.agents.prompts import LANGUAGE_INSTRUCTION_VI, build_debrief_prompt


def _activity() -> dict:
    return {
        "activity_name": "Morning run",
        "duration_sec": 3600,
        "distance_m": 12000.0,
        "sport_type": "Run",
        "tss": 70.0,
        "hr_tss": 72.0,
        "hr_drift_pct": 3.4,
        "aerobic_decoupling_pct": 4.1,
        "ngp_sec_km": 310.0,
        "zone_distribution": {"z1_pct": 5, "z2_pct": 70, "z3_pct": 15, "z4_pct": 8, "z5_pct": 2},
        "elevation_gain_m": 150,
        "cadence_avg": 178,
    }


def _context(language: str = "en") -> dict:
    return {
        "lthr": 162,
        "threshold_pace_sec_km": 270,
        "tss_30d_avg": 65.0,
        "acwr": 1.1,
        "ctl": 50.0,
        "atl": 55.0,
        "tsb": -5.0,
        "training_phase": "Build",
        "race_target": None,
        "planned_today": None,
        "planned_tomorrow": None,
        "language": language,
    }


def test_vietnamese_language_appends_instruction() -> None:
    prompt = build_debrief_prompt(_activity(), _context("vi"))
    assert LANGUAGE_INSTRUCTION_VI in prompt
    assert "Respond entirely in Vietnamese" in prompt


def test_english_language_omits_instruction() -> None:
    prompt = build_debrief_prompt(_activity(), _context("en"))
    assert LANGUAGE_INSTRUCTION_VI not in prompt
    assert "Vietnamese" not in prompt


def test_missing_language_key_defaults_to_english_behavior() -> None:
    ctx = _context()
    del ctx["language"]
    prompt = build_debrief_prompt(_activity(), ctx)
    assert LANGUAGE_INSTRUCTION_VI not in prompt
