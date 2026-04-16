from app.metrics.zones import hr_zone, pace_zone, zone_distribution


def test_hr_zone_z1() -> None:
    assert hr_zone(110, lthr=160) == 1


def test_hr_zone_z2() -> None:
    assert hr_zone(125, lthr=160) == 2


def test_hr_zone_z4() -> None:
    assert hr_zone(158, lthr=160) == 4


def test_hr_zone_z5() -> None:
    assert hr_zone(175, lthr=160) == 5


def test_pace_zone_z2() -> None:
    assert pace_zone(280, threshold_pace_sec_km=240) == 2


def test_zone_distribution_empty() -> None:
    assert zone_distribution([], lthr=160)["z1_pct"] == 0.0
