from eval.matrix import FixtureResult, ModeResult
from eval.ranking import composite_score, rank_variant
from eval.scorer import DeterministicScores


def _make_mode(det_total: int, coherence: int, coach_value: float) -> ModeResult:
    return ModeResult(
        mode="LLM",
        deterministic=DeterministicScores(
            specificity=det_total // 6,
            no_generics=det_total // 6,
            acwr_band=det_total // 6,
            nutrition_ratio=det_total // 6,
            vmm_math=det_total // 6,
            actionability=det_total - 5 * (det_total // 6),
        ),
        coherence=coherence,
        coach_value=coach_value,
        debrief={k: "" for k in ("load_verdict", "technical_insight", "next_session_action", "nutrition_protocol", "vmm_projection")},
    )


def test_composite_score_perfect() -> None:
    # det 18/18, coh 3/3, cv 5/5 → should be 100
    mode = _make_mode(18, 3, 5.0)
    assert composite_score(mode) == 100.0


def test_composite_score_zero() -> None:
    # det 0/18, coh 0/3, cv 1/5 → should be 0
    mode = _make_mode(0, 0, 1.0)
    assert composite_score(mode) == 0.0


def test_composite_score_middle() -> None:
    # det 9/18 (0.5), coh 1.5/3 (0.5), cv 3/5 (0.5) → 50
    mode = _make_mode(9, 1, 3.0)  # coh 1/3 = 0.333
    # det: 0.5 * 30 = 15
    # coh: 0.333 * 30 = 10
    # cv: 0.5 * 40 = 20
    # total: 45
    assert 44 <= composite_score(mode) <= 46


def test_composite_score_coach_value_weights_most() -> None:
    # Same det+coh; different coach_value
    low_cv = _make_mode(12, 2, 2.0)
    high_cv = _make_mode(12, 2, 5.0)
    assert composite_score(high_cv) > composite_score(low_cv)
    # difference should be 40% * (4/4 - 1/4) = 30 points
    assert abs((composite_score(high_cv) - composite_score(low_cv)) - 30.0) < 0.5


def test_rank_variant_averages_fixtures() -> None:
    r1 = FixtureResult(fixture_id="F1", fixture_name="a", llm=_make_mode(18, 3, 5.0), fallback=_make_mode(12, 2, 3.0))
    r2 = FixtureResult(fixture_id="F2", fixture_name="b", llm=_make_mode(12, 2, 3.0), fallback=_make_mode(6, 1, 2.0))
    rank = rank_variant("test_variant", [r1, r2])
    assert rank.variant == "test_variant"
    # r1=100, r2=60 (det 0.667*30=20 + coh 0.667*30=20 + cv 0.5*40=20) → avg 80
    assert 78 <= rank.llm_score <= 82
    assert rank.avg_coach_value == 4.0
    assert rank.avg_deterministic == 15.0


def test_rank_variant_empty_returns_zero() -> None:
    rank = rank_variant("empty", [])
    assert rank.llm_score == 0.0
    assert rank.avg_deterministic == 0.0
