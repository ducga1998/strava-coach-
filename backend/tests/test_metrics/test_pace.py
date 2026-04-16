from app.metrics.pace import grade_adjusted_pace, normalised_graded_pace


def test_gap_flat() -> None:
    gap = grade_adjusted_pace(velocity_ms=3.33, grade_pct=0.0)
    assert abs(gap - 300.0) < 5


def test_gap_uphill() -> None:
    gap_up = grade_adjusted_pace(velocity_ms=3.33, grade_pct=10.0)
    gap_flat = grade_adjusted_pace(velocity_ms=3.33, grade_pct=0.0)
    assert gap_up > gap_flat


def test_ngp_returns_float() -> None:
    result = normalised_graded_pace([3.0, 3.2, 3.1], [0.0, 5.0, -2.0])
    assert isinstance(result, float)
    assert result > 0
