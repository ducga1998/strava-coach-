"""Slope-segmented physiological metrics.

The descent-HR delta is a VMM-specific diagnostic (see PRD_COACHING.md §3):
on a descent, heart rate should *drop*. If it doesn't, the athlete is using
their quads as brakes — a high-injury-risk pattern for 160km mountain races.

All functions here are pure: numbers in, numbers out. No DB, no HTTP.
"""

from __future__ import annotations

CLIMB_GRADE_THRESHOLD_PCT = 3.0
DESCENT_GRADE_THRESHOLD_PCT = -3.0


def descent_hr_delta(
    hr_stream: list[float],
    altitude_stream: list[float],
    time_stream: list[float],
) -> float | None:
    """Compute ``avg_hr_descent - avg_hr_climb`` in bpm.

    Segments each sample by instantaneous grade (``dz/dt`` normalised to
    horizontal distance via a 1 m/s fallback when time deltas are zero):

    - grade > +3%  → climb
    - grade < -3%  → descent
    - otherwise    → flat (excluded)

    Returns ``None`` if any input stream is empty, if the three streams are
    too short to align, or if the activity lacks either a climb or descent
    section.

    Coaching thresholds:
        delta < 0 bpm   healthy — HR drops going down
        delta >  0 bpm  concern — quads absorbing shock
        delta > +8 bpm  red flag — poor descending economy, VMM-critical
    """
    if not hr_stream or not altitude_stream or not time_stream:
        return None

    length = min(len(hr_stream), len(altitude_stream), len(time_stream))
    if length < 2:
        return None

    climb_hr: list[float] = []
    descent_hr: list[float] = []

    for i in range(1, length):
        dt = time_stream[i] - time_stream[i - 1]
        if dt <= 0:
            # duplicate or non-monotonic timestamp — fall back to 1s spacing
            dt = 1.0
        dz = altitude_stream[i] - altitude_stream[i - 1]
        # Approximate horizontal distance with dt (GPS velocity unknown here).
        # For segmentation purposes the absolute scale doesn't matter; we only
        # care about the sign and relative magnitude of the slope.
        horizontal_m = max(dt, 0.1)
        grade_pct = dz / horizontal_m * 100.0

        hr = hr_stream[i]
        if hr <= 0:
            continue

        if grade_pct > CLIMB_GRADE_THRESHOLD_PCT:
            climb_hr.append(hr)
        elif grade_pct < DESCENT_GRADE_THRESHOLD_PCT:
            descent_hr.append(hr)

    if not climb_hr or not descent_hr:
        return None

    avg_climb = sum(climb_hr) / len(climb_hr)
    avg_descent = sum(descent_hr) / len(descent_hr)
    return round(avg_descent - avg_climb, 2)
