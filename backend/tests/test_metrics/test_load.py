from app.metrics.load import compute_acwr, compute_monotony_strain, update_ctl_atl


def test_ctl_increases_after_hard_day() -> None:
    ctl, _, _ = update_ctl_atl(prev_ctl=50.0, prev_atl=50.0, daily_tss=100.0)
    assert ctl > 50.0


def test_tsb_formula() -> None:
    ctl, atl, tsb = update_ctl_atl(prev_ctl=50.0, prev_atl=60.0, daily_tss=0.0)
    assert abs(tsb - (ctl - atl)) < 0.01


def test_acwr_healthy() -> None:
    assert 0.8 <= compute_acwr(acute_load=100, chronic_load=100) <= 1.0


def test_acwr_overload() -> None:
    assert compute_acwr(acute_load=160, chronic_load=100) > 1.5


def test_monotony() -> None:
    monotony, _ = compute_monotony_strain([80, 80, 80, 80, 80, 80, 80])
    assert monotony > 5


def test_strain() -> None:
    daily_loads = [80, 80, 80, 80, 80, 80, 80]
    monotony, strain = compute_monotony_strain(daily_loads)
    assert strain == sum(daily_loads) * monotony
