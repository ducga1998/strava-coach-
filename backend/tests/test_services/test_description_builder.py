from app.services.description_builder import (
    MAX_DESCRIPTION_CHARS,
    acwr_zone_label,
    format_strava_description,
)


def test_acwr_zone_label_underload() -> None:
    assert acwr_zone_label(0.5) == "underload"
    assert acwr_zone_label(0.79) == "underload"


def test_acwr_zone_label_green() -> None:
    assert acwr_zone_label(0.8) == "green"
    assert acwr_zone_label(1.0) == "green"
    assert acwr_zone_label(1.3) == "green"


def test_acwr_zone_label_caution() -> None:
    assert acwr_zone_label(1.31) == "caution"
    assert acwr_zone_label(1.5) == "caution"


def test_acwr_zone_label_injury_risk() -> None:
    assert acwr_zone_label(1.51) == "injury risk"
    assert acwr_zone_label(2.0) == "injury risk"


def test_format_strava_description_has_four_lines() -> None:
    result = format_strava_description(
        tss=82.0,
        acwr=1.12,
        z2_pct=68.0,
        hr_drift_pct=4.1,
        decoupling_pct=3.8,
        next_action="VMM 8w: 90' trail, downhill tech >15%",
        deep_dive_url="http://localhost:5173/activities/42?athlete_id=1",
    )
    assert len(result.split("\n")) == 4


def test_format_strava_description_line1_content() -> None:
    result = format_strava_description(
        tss=82.0, acwr=1.12, z2_pct=68.0,
        hr_drift_pct=4.1, decoupling_pct=3.8,
        next_action="Easy Z2", deep_dive_url="http://app/a/1",
    )
    line1 = result.split("\n")[0]
    assert "TSS 82" in line1
    assert "ACWR 1.12" in line1
    assert "(green)" in line1
    assert "Z2 68%" in line1


def test_format_strava_description_line2_content() -> None:
    result = format_strava_description(
        tss=82.0, acwr=1.12, z2_pct=68.0,
        hr_drift_pct=4.1, decoupling_pct=3.8,
        next_action="Easy Z2", deep_dive_url="http://app/a/1",
    )
    line2 = result.split("\n")[1]
    assert "HR drift 4.1%" in line2
    assert "decoupling 3.8%" in line2


def test_format_strava_description_line3_is_next_action() -> None:
    result = format_strava_description(
        tss=50.0, acwr=1.0, z2_pct=60.0,
        hr_drift_pct=3.0, decoupling_pct=2.0,
        next_action="VMM 8w: 90' trail, quad-load descents",
        deep_dive_url="http://app/a/2",
    )
    assert result.split("\n")[2] == "→ VMM 8w: 90' trail, quad-load descents"


def test_format_strava_description_line4_is_url() -> None:
    result = format_strava_description(
        tss=50.0, acwr=1.0, z2_pct=60.0,
        hr_drift_pct=3.0, decoupling_pct=2.0,
        next_action="Easy run", deep_dive_url="http://localhost:5173/activities/99?athlete_id=7",
    )
    assert result.split("\n")[3] == "🔍 http://localhost:5173/activities/99?athlete_id=7"


def test_format_strava_description_rounds_tss() -> None:
    result = format_strava_description(
        tss=82.7, acwr=1.0, z2_pct=50.0,
        hr_drift_pct=3.0, decoupling_pct=2.0,
        next_action="Easy Z2", deep_dive_url="http://app/a/1",
    )
    assert "TSS 83" in result


def test_format_strava_description_injury_risk_zone() -> None:
    result = format_strava_description(
        tss=120.0, acwr=1.6, z2_pct=20.0,
        hr_drift_pct=9.0, decoupling_pct=8.0,
        next_action="Recovery Z1", deep_dive_url="http://app/a/2",
    )
    assert "(injury risk)" in result


def test_format_strava_description_tolerates_none_metrics() -> None:
    """A new caller passing None for any numeric metric must not TypeError."""
    result = format_strava_description(
        tss=None,
        acwr=None,
        z2_pct=None,
        hr_drift_pct=None,
        decoupling_pct=None,
        next_action="Easy Z2",
        deep_dive_url="http://app/a/1",
    )
    assert "TSS 0" in result
    assert "ACWR 0.00" in result
    assert "(underload)" in result  # acwr 0.0 is below 0.8


def test_format_strava_description_truncates_when_too_long() -> None:
    """LLM output that blows past Strava's 4096-char limit must be truncated,
    keep the trailing deep-dive URL intact, and stay under the cap."""
    long_vmm = "x" * 5000  # would blow past the cap on its own
    url = "https://app.example.com/activities/42?athlete_id=1"
    result = format_strava_description(
        tss=100.0,
        acwr=1.0,
        z2_pct=60.0,
        hr_drift_pct=3.0,
        decoupling_pct=3.0,
        next_action="Easy Z2",
        deep_dive_url=url,
        vmm_projection=long_vmm,
    )
    assert len(result) <= MAX_DESCRIPTION_CHARS
    # Trailing URL line survives truncation so users can still click through.
    assert result.endswith(f"🔍 {url}")
    # Ellipsis marker appears before the URL line to signal truncation.
    assert "…" in result


def test_format_strava_description_under_limit_unchanged() -> None:
    """Short outputs must not be altered by the truncation path."""
    result = format_strava_description(
        tss=50.0,
        acwr=1.0,
        z2_pct=70.0,
        hr_drift_pct=2.0,
        decoupling_pct=1.5,
        next_action="Easy Z2",
        deep_dive_url="http://app/a/1",
    )
    assert "…" not in result
    assert len(result) < MAX_DESCRIPTION_CHARS
