from app.metrics.heart_rate import aerobic_decoupling, hr_drift, hr_tss


def test_hr_tss_easy_run() -> None:
    result = hr_tss([120] * 3600, lthr=160, duration_sec=3600)
    assert 40 < result < 70


def test_hr_drift_stable() -> None:
    assert abs(hr_drift([140] * 100)) < 2.0


def test_hr_drift_rising() -> None:
    heart_rate = [130] * 50 + [150] * 50
    assert hr_drift(heart_rate) > 5.0


def test_aerobic_decoupling() -> None:
    pace = [300.0] * 105
    heart_rate = list(range(130, 180)) + [179] * 55
    assert aerobic_decoupling(pace, heart_rate) > 0
