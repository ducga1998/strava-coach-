import math


def hr_tss(hr_stream: list[float], lthr: float, duration_sec: int) -> float:
    if not hr_stream or lthr <= 0 or duration_sec <= 0:
        return 0.0
    avg_hr = sum(hr_stream) / len(hr_stream)
    hr_ratio = avg_hr / lthr
    trimp_factor = hr_ratio * 0.64 * math.exp(1.92 * hr_ratio)
    hours = duration_sec / 3600.0
    return round(trimp_factor * hours * 100.0 / 3.0, 1)


def hr_drift(hr_stream: list[float]) -> float:
    if len(hr_stream) < 2:
        return 0.0
    first_half, second_half = _split_halves(hr_stream)
    first_avg = _mean(first_half)
    if first_avg == 0:
        return 0.0
    return round((_mean(second_half) - first_avg) / first_avg * 100.0, 2)


def aerobic_decoupling(pace_stream: list[float], hr_stream: list[float]) -> float:
    pace, heart_rate = _align_streams(pace_stream, hr_stream)
    if len(pace) < 2:
        return 0.0
    first_pace, second_pace = _split_halves(pace)
    first_hr, second_hr = _split_halves(heart_rate)
    first_efficiency = _efficiency_factor(first_pace, first_hr)
    if first_efficiency == 0:
        return 0.0
    second_efficiency = _efficiency_factor(second_pace, second_hr)
    return round((first_efficiency - second_efficiency) / first_efficiency * 100.0, 2)


def _split_halves(values: list[float]) -> tuple[list[float], list[float]]:
    midpoint = len(values) // 2
    return values[:midpoint], values[midpoint:]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _align_streams(
    pace_stream: list[float], hr_stream: list[float]
) -> tuple[list[float], list[float]]:
    length = min(len(pace_stream), len(hr_stream))
    return pace_stream[:length], hr_stream[:length]


def _efficiency_factor(pace_slice: list[float], hr_slice: list[float]) -> float:
    avg_pace = _mean([value for value in pace_slice if value > 0])
    avg_hr = _mean([value for value in hr_slice if value > 0])
    if avg_pace == 0 or avg_hr == 0:
        return 0.0
    return (1.0 / avg_pace) / avg_hr
