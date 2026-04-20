"""Composite scoring — blends deterministic + coherence + coach_value into 0-100 score."""
from dataclasses import dataclass

from eval.matrix import FixtureResult, ModeResult

WEIGHT_DETERMINISTIC = 0.30
WEIGHT_COHERENCE = 0.30
WEIGHT_COACH_VALUE = 0.40


def composite_score(mode: ModeResult) -> float:
    """Return 0-100 weighted score for a single mode result.

    Weights reflect what matters most:
    - coach_value (40%) is the ground truth for coaching quality
    - coherence (30%) is a safety check against contradictions
    - deterministic (30%) catches regressions on hard rules
    """
    det_normalized = mode.deterministic.total / 18
    coh_normalized = mode.coherence / 3
    cv_normalized = (mode.coach_value - 1) / 4
    weighted = (
        WEIGHT_DETERMINISTIC * det_normalized
        + WEIGHT_COHERENCE * coh_normalized
        + WEIGHT_COACH_VALUE * cv_normalized
    )
    return round(weighted * 100, 2)


@dataclass(frozen=True)
class VariantRank:
    variant: str
    llm_score: float
    fallback_score: float
    avg_deterministic: float
    avg_coherence: float
    avg_coach_value: float

    @property
    def rank_score(self) -> float:
        return self.llm_score


def rank_variant(variant_name: str, fixture_results: list[FixtureResult]) -> VariantRank:
    """Aggregate fixture-level scores into one variant-level score."""
    n = len(fixture_results)
    if n == 0:
        return VariantRank(variant_name, 0.0, 0.0, 0.0, 0.0, 0.0)
    llm_avg = sum(composite_score(r.llm) for r in fixture_results) / n
    fb_avg = sum(composite_score(r.fallback) for r in fixture_results) / n
    det_avg = sum(r.llm.deterministic.total for r in fixture_results) / n
    coh_avg = sum(r.llm.coherence for r in fixture_results) / n
    cv_avg = sum(r.llm.coach_value for r in fixture_results) / n
    return VariantRank(
        variant=variant_name,
        llm_score=round(llm_avg, 2),
        fallback_score=round(fb_avg, 2),
        avg_deterministic=round(det_avg, 2),
        avg_coherence=round(coh_avg, 2),
        avg_coach_value=round(cv_avg, 2),
    )
