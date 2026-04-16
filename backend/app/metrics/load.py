import statistics


CTL_TIME_CONSTANT_DAYS = 42
ATL_TIME_CONSTANT_DAYS = 7


def update_ctl_atl(
    prev_ctl: float, prev_atl: float, daily_tss: float
) -> tuple[float, float, float]:
    ctl = _ewma(prev_ctl, daily_tss, CTL_TIME_CONSTANT_DAYS)
    atl = _ewma(prev_atl, daily_tss, ATL_TIME_CONSTANT_DAYS)
    tsb = ctl - atl
    return round(ctl, 2), round(atl, 2), round(tsb, 2)


def compute_acwr(acute_load: float, chronic_load: float) -> float:
    if chronic_load <= 0:
        return 0.0
    return round(acute_load / chronic_load, 3)


def compute_monotony_strain(daily_loads: list[float]) -> tuple[float, float]:
    if len(daily_loads) < 2:
        return 0.0, 0.0
    monotony = _monotony(daily_loads)
    strain = round(sum(daily_loads) * monotony, 2)
    return monotony, strain


def _ewma(previous: float, current: float, time_constant_days: int) -> float:
    factor = 1.0 - 2.0 ** (-1.0 / time_constant_days)
    return previous + (current - previous) * factor


def _monotony(daily_loads: list[float]) -> float:
    stdev = statistics.stdev(daily_loads)
    if stdev == 0:
        return 999.0
    return round(statistics.mean(daily_loads) / stdev, 2)
