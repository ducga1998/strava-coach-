"""Tests for cadence-drop metric.

Coaching context (see PRD_COACHING.md §6):
    A drop > 5% from first-half to second-half cadence, filtered to
    actual running sections (velocity > 0.5 m/s so walk breaks don't
    skew the signal), is neuromuscular fatigue — the legs are losing
    spring even when the heart is still willing.
"""

from app.metrics.cadence import cadence_drop_pct


def test_cadence_drop_returns_none_when_stream_empty() -> None:
    assert cadence_drop_pct(cadence_stream=[], velocity_stream=[]) is None


def test_cadence_drop_returns_none_when_only_walking() -> None:
    """If velocity is always below 0.5 m/s, the athlete was walking — not a running metric."""
    cadence = [80.0] * 100  # 80 spm = single-leg cadence typical walk
    velocity = [0.2] * 100
    assert cadence_drop_pct(cadence, velocity) is None


def test_cadence_drop_zero_when_stable() -> None:
    """Rested athlete holds cadence across the whole run."""
    cadence = [170.0] * 200
    velocity = [3.0] * 200
    result = cadence_drop_pct(cadence, velocity)
    assert result is not None
    assert abs(result) < 0.5


def test_cadence_drop_positive_when_legs_fatigue() -> None:
    """Cadence drops from 170 → 155 spm by the end: classic neuromuscular fatigue."""
    cadence = [170.0] * 100 + [155.0] * 100
    velocity = [3.0] * 200
    result = cadence_drop_pct(cadence, velocity)
    assert result is not None
    # (170 - 155) / 170 * 100 = 8.82%
    assert 8.0 < result < 10.0


def test_cadence_drop_excludes_walk_break_samples() -> None:
    """Walk-break samples (velocity < 0.5 m/s) must not distort the average."""
    # Second half has 50 running samples @ 160 spm and 50 walk-break samples @ 60 spm.
    # If walk breaks aren't filtered, avg = 110; that would inflate the drop.
    cadence = [170.0] * 100 + ([160.0] * 50 + [60.0] * 50)
    velocity = [3.0] * 100 + ([3.0] * 50 + [0.1] * 50)
    result = cadence_drop_pct(cadence, velocity)
    assert result is not None
    # Filtered properly: (170 - 160) / 170 * 100 ≈ 5.88%
    assert 5.0 < result < 7.0


def test_cadence_drop_negative_when_athlete_speeds_up() -> None:
    """Negative result = cadence rose in second half (picked up the pace)."""
    cadence = [160.0] * 100 + [172.0] * 100
    velocity = [3.0] * 200
    result = cadence_drop_pct(cadence, velocity)
    assert result is not None
    assert result < -5.0


def test_cadence_drop_returns_none_when_no_running_samples() -> None:
    """Cadence given but velocity filter leaves no running samples."""
    cadence = [170.0] * 100
    velocity = [0.0] * 100
    assert cadence_drop_pct(cadence, velocity) is None


def test_cadence_drop_returns_none_when_half_empty() -> None:
    """Every running sample falls in one half only — cannot compute delta."""
    # All running is in first half; second half is walking (filtered out).
    cadence = [170.0] * 100 + [0.0] * 100
    velocity = [3.0] * 100 + [0.0] * 100
    assert cadence_drop_pct(cadence, velocity) is None


def test_cadence_drop_handles_zero_cadence_readings() -> None:
    """Zero-cadence samples (device artefacts) excluded from averaging."""
    cadence = [170.0] * 50 + [0.0] * 50 + [165.0] * 100
    velocity = [3.0] * 200
    result = cadence_drop_pct(cadence, velocity)
    assert result is not None
    # First half averages 170 (ignoring zeros), second half = 165. Drop ≈ 2.94%.
    assert 2.0 < result < 4.0
