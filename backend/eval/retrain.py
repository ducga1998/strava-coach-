"""Re-training: run eval on every prompt variant, rank, promote winner.

Usage:
    cd backend
    python -m eval.retrain                       # run all variants, rank, ask to promote
    python -m eval.retrain --auto-promote        # promote winner if it beats current
    python -m eval.retrain --fixtures=F2,F4      # subset fixtures (cheaper iteration)
    python -m eval.retrain --dry-run             # skip all LLM calls; just show variants
"""
import argparse
import asyncio
import importlib
import logging
import re
from datetime import datetime
from pathlib import Path

from eval.fixtures import ALL_FIXTURES, get_fixture
from eval.matrix import FixtureResult
from eval.ranking import VariantRank, rank_variant
from eval.runner import run_fixture

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def discover_variants(prompts_dir: Path | None = None) -> list[str]:
    """Return sorted variant names from eval/prompts/*.py (excluding __init__)."""
    if prompts_dir is None:
        prompts_dir = Path(__file__).parent / "prompts"
    variants = [
        p.stem for p in prompts_dir.glob("*.py")
        if p.stem != "__init__"
    ]
    return sorted(variants)


async def run_variant(variant_name: str, fixtures) -> list[FixtureResult]:
    """Run eval on one variant across the given fixtures."""
    results = []
    for fixture in fixtures:
        logger.info("  [%s] fixture %s", variant_name, fixture.id)
        result = await run_fixture(fixture, prompt_variant=variant_name)
        results.append(result)
    return results


async def run_all_variants(variant_names: list[str], fixtures) -> list[VariantRank]:
    """Run eval on every variant, return list sorted by score (best first)."""
    ranks = []
    for name in variant_names:
        logger.info("Running variant: %s", name)
        fixture_results = await run_variant(name, fixtures)
        ranks.append(rank_variant(name, fixture_results))
    ranks.sort(key=lambda r: r.rank_score, reverse=True)
    return ranks


def render_leaderboard(ranks: list[VariantRank]) -> str:
    lines = [
        "# Retrain Leaderboard",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "| Rank | Variant | LLM score | Fallback score | Det avg | Coh avg | Coach avg |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(ranks, start=1):
        marker = " 🏆" if i == 1 else ""
        lines.append(
            f"| {i}{marker} | `{r.variant}` | **{r.llm_score:.1f}**/100 | "
            f"{r.fallback_score:.1f}/100 | {r.avg_deterministic:.1f}/18 | "
            f"{r.avg_coherence:.1f}/3 | {r.avg_coach_value:.2f}/5 |"
        )
    return "\n".join(lines)


def _extract_variant_system_prompt(variant_name: str) -> str:
    module = importlib.import_module(f"eval.prompts.{variant_name}")
    prompt = module.SYSTEM_PROMPT
    if not isinstance(prompt, str) or not prompt.strip():
        raise RuntimeError(f"Variant {variant_name} has empty SYSTEM_PROMPT")
    return prompt


_PROMPT_REGEX = re.compile(
    r'^(SYSTEM_PROMPT\s*=\s*""")(.*?)(""")',
    re.MULTILINE | re.DOTALL,
)


def promote_variant(variant_name: str, prompts_file: Path | None = None) -> None:
    """Overwrite SYSTEM_PROMPT in app/agents/prompts.py with variant's content."""
    if prompts_file is None:
        prompts_file = Path(__file__).parent.parent / "app" / "agents" / "prompts.py"

    new_prompt = _extract_variant_system_prompt(variant_name)
    source = prompts_file.read_text()

    def _replace(match: re.Match[str]) -> str:
        return match.group(1) + "\n" + new_prompt.strip() + "\n" + match.group(3)

    updated = _PROMPT_REGEX.sub(_replace, source, count=1)
    if updated == source:
        raise RuntimeError(
            f"Could not find SYSTEM_PROMPT triple-quoted block in {prompts_file}"
        )
    prompts_file.write_text(updated)


def _resolve_fixtures(fixtures_arg: str):
    if fixtures_arg == "all":
        return list(ALL_FIXTURES)
    return [get_fixture(fid.strip()) for fid in fixtures_arg.split(",")]


async def main_async(args: argparse.Namespace) -> tuple[list[VariantRank], str]:
    variants = discover_variants()
    if not variants:
        raise SystemExit("No variants found in eval/prompts/")
    logger.info("Discovered %d variant(s): %s", len(variants), variants)

    if args.dry_run:
        return [], f"Would rank {len(variants)} variants: {variants}"

    fixtures = _resolve_fixtures(args.fixtures)
    ranks = await run_all_variants(variants, fixtures)
    leaderboard = render_leaderboard(ranks)
    return ranks, leaderboard


def save_report(leaderboard: str) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    report_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "superpowers" / "eval-runs"
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"{timestamp}_retrain-leaderboard.md"
    path.write_text(leaderboard)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrain: rank all prompt variants and optionally promote winner")
    parser.add_argument("--fixtures", default="all", help="Comma-sep fixture ids (F1,F2,...) or 'all'")
    parser.add_argument("--auto-promote", action="store_true", help="Promote winner without prompting")
    parser.add_argument("--dry-run", action="store_true", help="Just show discovered variants, no LLM calls")
    parser.add_argument("--no-save", action="store_true", help="Don't save leaderboard to disk")
    args = parser.parse_args()

    ranks, leaderboard = asyncio.run(main_async(args))
    print(leaderboard)

    if args.dry_run or not ranks:
        return

    if not args.no_save:
        path = save_report(leaderboard)
        print(f"\n✓ Leaderboard saved to: {path}")

    winner = ranks[0]
    print(f"\n🏆 Winner: {winner.variant} (score {winner.llm_score:.1f}/100)")

    current_score = next((r.llm_score for r in ranks if r.variant == "current"), None)
    if current_score is None:
        print("  (no 'current' variant present for comparison)")
        return

    if winner.variant == "current":
        print("  ✓ Current production prompt is already best.")
        return

    delta = winner.llm_score - current_score
    print(f"  Current: {current_score:.1f} → winner: {winner.llm_score:.1f} (+{delta:.1f})")

    if delta <= 0:
        print("  ✗ No variant beats current. Skipping promotion.")
        return

    if args.auto_promote:
        promote_variant(winner.variant)
        print(f"  ✓ Promoted {winner.variant} → app/agents/prompts.py")
    else:
        print(f"\n  To promote: python -m eval.retrain --auto-promote")


if __name__ == "__main__":
    main()
