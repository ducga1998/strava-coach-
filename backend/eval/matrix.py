from dataclasses import dataclass

from eval.scorer import DeterministicScores


@dataclass(frozen=True)
class ModeResult:
    mode: str  # "LLM" or "Fallback"
    deterministic: DeterministicScores
    coherence: int
    coach_value: float
    debrief: dict[str, str]


@dataclass(frozen=True)
class FixtureResult:
    fixture_id: str
    fixture_name: str
    llm: ModeResult
    fallback: ModeResult


def render_matrix(results: list[FixtureResult], prompt_variant: str) -> str:
    lines = [
        f"# Debrief Eval Report — prompt variant: `{prompt_variant}`",
        "",
        "## Per-fixture scores",
        "",
        "| Fixture | Dimension | LLM | Fallback |",
        "|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| **{r.fixture_id}** {r.fixture_name} | Specificity | {r.llm.deterministic.specificity}/3 | {r.fallback.deterministic.specificity}/3 |")
        lines.append(f"|  | No generics | {r.llm.deterministic.no_generics}/3 | {r.fallback.deterministic.no_generics}/3 |")
        lines.append(f"|  | ACWR band | {r.llm.deterministic.acwr_band}/3 | {r.fallback.deterministic.acwr_band}/3 |")
        lines.append(f"|  | Nutrition ratio | {r.llm.deterministic.nutrition_ratio}/3 | {r.fallback.deterministic.nutrition_ratio}/3 |")
        lines.append(f"|  | VMM math | {r.llm.deterministic.vmm_math}/3 | {r.fallback.deterministic.vmm_math}/3 |")
        lines.append(f"|  | Actionability | {r.llm.deterministic.actionability}/3 | {r.fallback.deterministic.actionability}/3 |")
        lines.append(f"|  | Coherence | {r.llm.coherence}/3 | {r.fallback.coherence}/3 |")
        lines.append(f"|  | Coach value | {r.llm.coach_value:.1f}/5 | {r.fallback.coach_value:.1f}/5 |")
        lines.append(f"|  | **Deterministic total** | **{r.llm.deterministic.total}/18** | **{r.fallback.deterministic.total}/18** |")

    lines += ["", "## Average across fixtures", ""]
    n = len(results)
    if n > 0:
        avg_llm_det = sum(r.llm.deterministic.total for r in results) / n
        avg_fb_det = sum(r.fallback.deterministic.total for r in results) / n
        avg_llm_coh = sum(r.llm.coherence for r in results) / n
        avg_fb_coh = sum(r.fallback.coherence for r in results) / n
        avg_llm_cv = sum(r.llm.coach_value for r in results) / n
        avg_fb_cv = sum(r.fallback.coach_value for r in results) / n
        lines += [
            "| Metric | LLM avg | Fallback avg |",
            "|---|---|---|",
            f"| Deterministic | {avg_llm_det:.1f}/18 | {avg_fb_det:.1f}/18 |",
            f"| Coherence | {avg_llm_coh:.1f}/3 | {avg_fb_coh:.1f}/3 |",
            f"| Coach value | {avg_llm_cv:.2f}/5 | {avg_fb_cv:.2f}/5 |",
        ]

    lines += ["", "## Raw debrief outputs", ""]
    for r in results:
        lines += [f"### {r.fixture_id} — {r.fixture_name}", "", "**LLM mode:**", "```"]
        for k, v in r.llm.debrief.items():
            lines.append(f"{k}: {v}")
        lines += ["```", "", "**Fallback mode:**", "```"]
        for k, v in r.fallback.debrief.items():
            lines.append(f"{k}: {v}")
        lines += ["```", ""]

    return "\n".join(lines)
