from typing import TypedDict

from app.metrics.heart_rate import aerobic_decoupling, hr_drift, hr_tss
from app.metrics.pace import grade_adjusted_pace, normalised_graded_pace
from app.metrics.zones import ZoneDistribution, zone_distribution


class StreamValue(TypedDict, total=False):
    data: list[object]


Streams = dict[str, StreamValue]


class ActivityMetricsResult(TypedDict):
    hr_tss: float
    hr_drift_pct: float
    aerobic_decoupling_pct: float
    ngp_sec_km: float
    gap_avg_sec_km: float
    zone_distribution: ZoneDistribution


def compute_activity_metrics(
    streams: Streams,
    duration_sec: int,
    lthr: float,
    threshold_pace_sec_km: float,
) -> ActivityMetricsResult:
    heart_rate = _number_stream(streams, "heartrate")
    velocity = _number_stream(streams, "velocity_smooth")
    altitude = _number_stream(streams, "altitude")
    pace = _pace_stream(velocity, threshold_pace_sec_km)
    grades = _grade_stream(velocity, altitude)
    return {
        "hr_tss": hr_tss(heart_rate, lthr, duration_sec),
        "hr_drift_pct": hr_drift(heart_rate),
        "aerobic_decoupling_pct": aerobic_decoupling(pace, heart_rate),
        "ngp_sec_km": normalised_graded_pace(velocity, grades),
        "gap_avg_sec_km": _gap_average(velocity, grades),
        "zone_distribution": zone_distribution(heart_rate, lthr),
    }


def _number_stream(streams: Streams, key: str) -> list[float]:
    raw = streams.get(key, {}).get("data", [])
    return [float(value) for value in raw if isinstance(value, int | float)]


def _pace_stream(velocity: list[float], fallback: float) -> list[float]:
    return [1000.0 / value if value > 0 else fallback for value in velocity]


def _grade_stream(velocity: list[float], altitude: list[float]) -> list[float]:
    if not altitude:
        return [0.0 for _ in velocity]
    grades = [0.0]
    for index in range(1, min(len(velocity), len(altitude))):
        distance = max(velocity[index - 1], 0.1)
        grades.append((altitude[index] - altitude[index - 1]) / distance * 100.0)
    return grades


def _gap_average(velocity: list[float], grades: list[float]) -> float:
    values = [
        grade_adjusted_pace(speed, grade)
        for speed, grade in zip(velocity, grades, strict=False)
    ]
    return round(sum(values) / len(values), 2) if values else 0.0
