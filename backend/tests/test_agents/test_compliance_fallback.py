from datetime import date

from app.agents.debrief_graph import compute_plan_compliance
from app.agents.schema import PlannedWorkoutContext


def _planned(workout_type: str, tss: float | None, duration: int | None) -> PlannedWorkoutContext:
    return PlannedWorkoutContext(
        date=date(2026, 4, 22),
        workout_type=workout_type,
        planned_tss=tss,
        planned_duration_min=duration,
    )


def test_perfect_match_scores_high():
    planned = _planned("easy", 50, 45)
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=50,
        actual_duration_min=45,
        zone_distribution={"z3_pct": 5, "z4_pct": 2, "z5_pct": 0},
    )
    assert score >= 95
    assert headline == "On target."


def test_overcooked_easy_day_penalises_type_break_and_tss():
    planned = _planned("easy", 50, 45)
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=120,        # 240% of 50 → delta 1.40, clamped to 1.0 → -40
        actual_duration_min=55, # 22% over  → -6.6
        zone_distribution={"z3_pct": 30, "z4_pct": 15, "z5_pct": 5},  # Z3-5 = 50% → type break (-30)
    )
    assert score <= 30
    assert "Overcooked" in headline


def test_undertrained_day():
    planned = _planned("long", 180, 240)
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=60,          # 33% of planned → -26.8
        actual_duration_min=80, # 33% of planned → -20
        zone_distribution={"z3_pct": 5, "z4_pct": 1, "z5_pct": 0},
    )
    # Long + duration < 75% planned = TYPE BREAK
    assert score <= 40
    assert ("underdelivered" in headline.lower()) or ("TYPE BREAK" in headline)


def test_skipped_quality_session_type_break():
    planned = _planned("interval", 95, 75)
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=55,
        actual_duration_min=70,
        zone_distribution={"z3_pct": 3, "z4_pct": 1, "z5_pct": 0},  # Z3-5 = 4% → skipped quality
    )
    assert "TYPE BREAK" in headline or "quality" in headline.lower()
    assert score < 80


def test_missing_planned_numbers_still_scores_type_axis():
    planned = _planned("recovery", None, None)
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=120,
        actual_duration_min=90,
        zone_distribution={"z3_pct": 25, "z4_pct": 10, "z5_pct": 5},
    )
    # No TSS or duration penalties possible; type break = -30
    assert score == 70


def test_compliance_string_format_matches_contract():
    from app.agents.debrief_graph import format_plan_compliance_string

    planned = _planned("easy", 50, 45)
    result = format_plan_compliance_string(
        planned=planned,
        actual_tss=50,
        actual_duration_min=45,
        zone_distribution={"z3_pct": 5, "z4_pct": 2, "z5_pct": 0},
    )
    assert result.startswith("100/100 ") or result.startswith("99/100 ") or result.startswith("98/100 ")
    assert len(result.split(" ", 1)[1]) > 0


def test_skipped_workout_with_zero_actuals_is_penalised():
    """Regression: previously the scoring short-circuited when actual_tss
    or actual_duration_min were falsy (0), so a planned 180-TSS long run
    executed as a skipped 0-TSS 0-min activity scored 100/100 "On target."
    Now the TSS and duration deltas are computed against 0 actuals, giving
    full -40/-30 penalties."""
    planned = _planned("long", 180, 240)
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=0,
        actual_duration_min=0,
        zone_distribution={"z3_pct": 0, "z4_pct": 0, "z5_pct": 0},
    )
    # TSS axis: delta = |0 - 180| / 180 = 1.0 → -40
    # Duration axis: delta = |0 - 240| / 240 = 1.0 → -30
    # Type fidelity: planned long, actual duration 0 < 0.75 * 240 → TYPE BREAK (-30)
    # Total: 100 - 40 - 30 - 30 = 0
    assert score == 0
    assert "On target." not in headline


def test_zero_tss_against_easy_planned_still_penalised():
    """A 0-TSS 0-min execution against a planned easy day (no TYPE BREAK
    triggered from either easy or quality fidelity rules) still loses
    points on the TSS+duration axes."""
    planned = _planned("easy", 50, 45)
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=0,
        actual_duration_min=0,
        zone_distribution={"z3_pct": 0, "z4_pct": 0, "z5_pct": 0},
    )
    # TSS: -40. Duration: -30. No TYPE BREAK. → 30
    assert score == 30
    assert "underdelivered" in headline.lower()
