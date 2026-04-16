ZoneDistribution = dict[str, float]


def hr_zone(hr: float, lthr: float) -> int:
    if lthr <= 0:
        return 1
    pct = hr / lthr
    if pct < 0.72:
        return 1
    if pct < 0.82:
        return 2
    if pct < 0.90:
        return 3
    if pct < 1.05:
        return 4
    return 5


def pace_zone(pace_sec_km: float, threshold_pace_sec_km: float) -> int:
    if threshold_pace_sec_km <= 0:
        return 1
    pct = pace_sec_km / threshold_pace_sec_km
    if pct > 1.29:
        return 1
    if pct > 1.10:
        return 2
    if pct > 1.00:
        return 3
    if pct >= 0.95:
        return 4
    return 5


def zone_distribution(hr_stream: list[float], lthr: float) -> ZoneDistribution:
    if not hr_stream:
        return _empty_distribution()
    counts = {zone: 0 for zone in range(1, 6)}
    for heart_rate in hr_stream:
        counts[hr_zone(heart_rate, lthr)] += 1
    return _percentages(counts, len(hr_stream))


def _empty_distribution() -> ZoneDistribution:
    return {f"z{zone}_pct": 0.0 for zone in range(1, 6)}


def _percentages(counts: dict[int, int], total: int) -> ZoneDistribution:
    return {
        f"z{zone}_pct": round(counts[zone] / total * 100.0, 1)
        for zone in range(1, 6)
    }
