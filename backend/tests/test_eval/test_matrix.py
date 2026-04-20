from eval.matrix import FixtureResult, ModeResult, render_matrix
from eval.scorer import DeterministicScores


def _make_mode(label: str) -> ModeResult:
    return ModeResult(
        mode=label,
        deterministic=DeterministicScores(
            specificity=3, no_generics=3, acwr_band=3,
            nutrition_ratio=3, vmm_math=3, actionability=3,
        ),
        coherence=3,
        coach_value=4.2,
        debrief={
            "load_verdict": "TSS 110.",
            "technical_insight": "HR drift 9%.",
            "next_session_action": "60 min Z2.",
            "nutrition_protocol": "4:1.",
            "vmm_projection": "20h30m.",
        },
    )


def test_render_matrix_includes_all_dimensions() -> None:
    results = [
        FixtureResult(
            fixture_id="F2",
            fixture_name="Overreach",
            llm=_make_mode("LLM"),
            fallback=_make_mode("Fallback"),
        )
    ]
    output = render_matrix(results, prompt_variant="current")
    assert "F2" in output
    assert "Specificity" in output
    assert "Coherence" in output
    assert "Coach value" in output
    assert "current" in output


def test_render_matrix_aggregates_average() -> None:
    results = [
        FixtureResult(fixture_id="F1", fixture_name="Easy", llm=_make_mode("LLM"), fallback=_make_mode("Fallback")),
        FixtureResult(fixture_id="F2", fixture_name="Hard", llm=_make_mode("LLM"), fallback=_make_mode("Fallback")),
    ]
    output = render_matrix(results, prompt_variant="current")
    assert "Average" in output
