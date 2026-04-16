def grade_adjusted_pace(velocity_ms: float, grade_pct: float) -> float:
    if velocity_ms <= 0:
        return 0.0
    cost_ratio = _minetti_cost_ratio(grade_pct)
    effective_velocity = velocity_ms / cost_ratio
    if effective_velocity <= 0:
        return 0.0
    return 1000.0 / effective_velocity


def normalised_graded_pace(
    velocity_stream: list[float], grade_stream: list[float], window: int = 30
) -> float:
    if not velocity_stream:
        return 0.0
    gap_values = _gap_values(velocity_stream, grade_stream)
    smoothed = _rolling_mean([value**4 for value in gap_values], window)
    if not smoothed:
        return 0.0
    return (sum(smoothed) / len(smoothed)) ** 0.25


def _minetti_cost_ratio(grade_pct: float) -> float:
    grade = grade_pct / 100.0
    ratio = (
        155.4 * grade**5
        - 30.4 * grade**4
        - 43.3 * grade**3
        + 46.3 * grade**2
        + 19.5 * grade
        + 3.6
    ) / 3.6
    return max(ratio, 0.1)


def _gap_values(velocity_stream: list[float], grade_stream: list[float]) -> list[float]:
    return [
        grade_adjusted_pace(velocity, grade)
        for velocity, grade in zip(velocity_stream, grade_stream, strict=False)
    ]


def _rolling_mean(values: list[float], window: int) -> list[float]:
    smoothed: list[float] = []
    for index in range(len(values)):
        start = max(0, index - window + 1)
        segment = values[start : index + 1]
        smoothed.append(sum(segment) / len(segment))
    return smoothed
