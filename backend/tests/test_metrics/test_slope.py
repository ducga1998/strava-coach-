"""Tests for slope-segmented metrics (descent HR delta).

Coaching context (see PRD_COACHING.md §3):
    descent_hr_delta = avg_hr_descents - avg_hr_climbs

- Negative: normal — HR drops going down.
- Near zero: quads absorbing shock, braking hard.
- Positive: quad weakness / poor descending economy — VMM red flag.

Grade segmentation:
- climb   > +3%
- descent < -3%
- flat    otherwise
"""

from app.metrics.slope import descent_hr_delta


def test_descent_hr_delta_returns_none_when_no_hr() -> None:
    assert descent_hr_delta(hr_stream=[], altitude_stream=[1, 2, 3], time_stream=[0, 1, 2]) is None


def test_descent_hr_delta_returns_none_when_no_altitude() -> None:
    assert descent_hr_delta(hr_stream=[140, 150, 145], altitude_stream=[], time_stream=[0, 1, 2]) is None


def test_descent_hr_delta_returns_none_without_climb_section() -> None:
    # Flat course throughout, no segments qualify as climbs
    altitudes = [100.0] * 120
    heart_rate = [150.0] * 120
    time_stream = list(range(120))
    assert descent_hr_delta(heart_rate, altitudes, time_stream) is None


def test_descent_hr_delta_returns_none_without_descent_section() -> None:
    # Pure climb, no descent section
    altitudes = [100.0 + i for i in range(120)]  # +1m/sec = steep climb
    heart_rate = [160.0] * 120
    time_stream = list(range(120))
    assert descent_hr_delta(heart_rate, altitudes, time_stream) is None


def test_descent_hr_delta_negative_when_hr_drops_on_descent() -> None:
    """Healthy pattern: HR drops on the way down."""
    # First 60s: climb at +10% grade, HR 170
    # Next 60s: descent at -10% grade, HR 135
    time_stream = list(range(120))
    altitudes = [float(i) for i in range(60)] + [60.0 - (i + 1) for i in range(60)]
    heart_rate = [170.0] * 60 + [135.0] * 60
    result = descent_hr_delta(heart_rate, altitudes, time_stream)
    assert result is not None
    assert result < -20.0


def test_descent_hr_delta_positive_when_hr_rises_on_downhill() -> None:
    """VMM-critical signal: HR rises going downhill — quad weakness.

    This test exists because this is the single most important metric
    for VMM 160km preparation. See PRD_COACHING.md §3.
    """
    time_stream = list(range(120))
    altitudes = [float(i) for i in range(60)] + [60.0 - (i + 1) for i in range(60)]
    heart_rate = [150.0] * 60 + [162.0] * 60
    result = descent_hr_delta(heart_rate, altitudes, time_stream)
    assert result is not None
    assert result > 10.0


def test_descent_hr_delta_near_zero_when_hr_equal_on_both() -> None:
    """Quads working as brakes — HR unchanged despite going down."""
    time_stream = list(range(120))
    altitudes = [float(i) for i in range(60)] + [60.0 - (i + 1) for i in range(60)]
    heart_rate = [155.0] * 120
    result = descent_hr_delta(heart_rate, altitudes, time_stream)
    assert result is not None
    assert abs(result) < 1.0


def test_descent_hr_delta_ignores_flat_samples() -> None:
    """Flat sections (|grade| <= 3%) must not pollute climb or descent averages."""
    # Build altitude stream with clean transitions:
    # - samples  0-40   : climb at +5m/s  (steep climb throughout)
    # - samples 41-80   : flat           (no change)
    # - samples 81-121  : descent at -5m/s
    # HR markers:
    #   170 bpm on climbs, 999 bpm on flat (poison value), 140 bpm on descents.
    time_stream = list(range(122))
    altitudes = (
        [float(i) * 5.0 for i in range(41)]           # 0..200 climbing
        + [200.0] * 40                                 # flat at 200
        + [200.0 - (i + 1) * 5.0 for i in range(41)]  # 195..-5 descending
    )
    heart_rate = [170.0] * 41 + [999.0] * 40 + [140.0] * 41
    result = descent_hr_delta(heart_rate, altitudes, time_stream)
    # delta = 140 - 170 = -30 — flat's 999 must NOT contaminate either side.
    assert result is not None
    assert -35.0 < result < -25.0


def test_descent_hr_delta_handles_zero_time_deltas() -> None:
    """Duplicate time stamps must not raise (division-by-zero guard)."""
    time_stream = [0, 0, 1, 2, 3, 4]
    altitudes = [100.0, 100.0, 105.0, 110.0, 95.0, 90.0]
    heart_rate = [150.0, 150.0, 170.0, 170.0, 140.0, 140.0]
    result = descent_hr_delta(heart_rate, altitudes, time_stream)
    # should not raise; returns a value
    assert result is not None
