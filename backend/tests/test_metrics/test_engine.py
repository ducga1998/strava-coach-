from app.metrics.engine import compute_activity_metrics


def test_compute_returns_all_keys() -> None:
    streams = {
        "heartrate": {"data": [140] * 600},
        "velocity_smooth": {"data": [3.0] * 600},
        "altitude": {"data": [100 + index * 0.1 for index in range(600)]},
        "time": {"data": list(range(600))},
    }
    result = compute_activity_metrics(
        streams=streams,
        duration_sec=600,
        lthr=160,
        threshold_pace_sec_km=300,
    )
    expected = {
        "hr_tss",
        "hr_drift_pct",
        "aerobic_decoupling_pct",
        "ngp_sec_km",
        "zone_distribution",
    }
    assert expected.issubset(result.keys())
