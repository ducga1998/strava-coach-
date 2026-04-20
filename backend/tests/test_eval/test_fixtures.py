import pytest

from eval.fixtures import ALL_FIXTURES, get_fixture


def test_all_five_fixtures_present() -> None:
    assert {f.id for f in ALL_FIXTURES} == {"F1", "F2", "F3", "F4", "F5"}


def test_fixture_has_required_signal_keys() -> None:
    fixture = get_fixture("F2")
    required = {
        "acwr_band",
        "expected_carb_protein_ratio",
        "must_flag_junk_miles",
        "must_flag_vert_debt",
        "must_recommend_deload",
        "must_recommend_volume_increase",
    }
    assert required <= set(fixture.expected_signals.keys())


def test_get_fixture_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_fixture("F99")


def test_fixture_tss_matches_ratio_signal() -> None:
    """Self-consistency: every fixture's TSS must match its expected_carb_protein_ratio."""
    for fixture in ALL_FIXTURES:
        expected = "4:1" if fixture.activity.tss >= 100 else "3:1"
        assert fixture.expected_signals["expected_carb_protein_ratio"] == expected, (
            f"{fixture.id}: TSS {fixture.activity.tss} requires {expected}"
        )
