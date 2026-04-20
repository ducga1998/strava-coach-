from app.services.description_builder import acwr_zone_label, format_strava_description


def _full_kwargs(**overrides) -> dict:
    base = dict(
        tss=82.0,
        acwr=1.12,
        z2_pct=68.0,
        hr_drift_pct=4.1,
        decoupling_pct=3.8,
        next_action="90' trail, quad-load descents",
        deep_dive_url="http://app/a/42?athlete_id=1",
        feedback_url="http://app/feedback/42?athlete_id=1",
        nutrition_protocol="60g carb/h, mỗi 20p",
        vmm_projection="vững aerobic, cần nhiều descent hơn",
    )
    base.update(overrides)
    return base


def test_acwr_zone_label_underload() -> None:
    assert acwr_zone_label(0.5) == "underload"
    assert acwr_zone_label(0.79) == "underload"


def test_acwr_zone_label_green() -> None:
    assert acwr_zone_label(0.8) == "green"
    assert acwr_zone_label(1.3) == "green"


def test_acwr_zone_label_caution() -> None:
    assert acwr_zone_label(1.31) == "caution"
    assert acwr_zone_label(1.5) == "caution"


def test_acwr_zone_label_injury_risk() -> None:
    assert acwr_zone_label(1.51) == "injury risk"


def test_metrics_block_has_first_line_with_tss_acwr() -> None:
    result = format_strava_description(**_full_kwargs())
    first_line = result.splitlines()[0]
    assert "TSS 82" in first_line
    assert "ACWR 1.12" in first_line
    assert "green" in first_line


def test_metrics_block_second_line_has_z2_drift_decoupling() -> None:
    result = format_strava_description(**_full_kwargs())
    second_line = result.splitlines()[1]
    assert "Z2 68%" in second_line
    assert "HR drift 4.1%" in second_line
    assert "Decoupling 3.8%" in second_line


def test_coaching_block_present_when_nutrition_and_projection_provided() -> None:
    result = format_strava_description(**_full_kwargs())
    assert "Fuel: 60g carb/h, mỗi 20p" in result
    assert "VMM: vững aerobic, cần nhiều descent hơn" in result


def test_next_line_prefixed_with_arrow() -> None:
    result = format_strava_description(**_full_kwargs(next_action="Easy Z2 60'"))
    assert "→ Next: Easy Z2 60'" in result


def test_divider_and_links_at_bottom() -> None:
    result = format_strava_description(**_full_kwargs())
    lines = result.splitlines()
    divider_idx = next(i for i, ln in enumerate(lines) if set(ln) == {"─"})
    assert "Deep dive" in lines[divider_idx + 1]
    assert "Feedback" in lines[divider_idx + 2]


def test_feedback_url_appears_on_its_own_line() -> None:
    result = format_strava_description(
        **_full_kwargs(feedback_url="http://app/feedback/99?athlete_id=7")
    )
    lines = result.splitlines()
    feedback_line = next(ln for ln in lines if "Feedback" in ln)
    assert "http://app/feedback/99?athlete_id=7" in feedback_line


def test_deep_dive_url_appears_on_its_own_line() -> None:
    result = format_strava_description(**_full_kwargs(deep_dive_url="http://app/a/99"))
    lines = result.splitlines()
    deep_line = next(ln for ln in lines if "Deep dive" in ln)
    assert "http://app/a/99" in deep_line


def test_coaching_block_omitted_when_both_empty_no_double_blank() -> None:
    result = format_strava_description(
        **_full_kwargs(nutrition_protocol="", vmm_projection="")
    )
    assert "Fuel:" not in result
    assert "VMM:" not in result
    assert "\n\n\n" not in result


def test_next_line_omitted_when_next_action_empty() -> None:
    result = format_strava_description(**_full_kwargs(next_action=""))
    assert "→ Next:" not in result
    assert "\n\n\n" not in result


def test_tss_rounds_to_int() -> None:
    result = format_strava_description(**_full_kwargs(tss=82.7))
    assert "TSS 83" in result


def test_injury_risk_zone_appears_in_first_line() -> None:
    result = format_strava_description(**_full_kwargs(acwr=1.6))
    first_line = result.splitlines()[0]
    assert "injury risk" in first_line
