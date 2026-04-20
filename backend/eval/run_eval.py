"""CLI: run eval suite, print matrix, optionally save report.

Usage:
    cd backend
    python -m eval.run_eval                         # all fixtures, current prompt
    python -m eval.run_eval --fixture=F2            # single fixture
    python -m eval.run_eval --prompt=variant_v2     # different prompt module
    python -m eval.run_eval --save-report           # save to docs/superpowers/eval-runs/
"""
import argparse
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from eval.fixtures import ALL_FIXTURES, get_fixture
from eval.matrix import render_matrix
from eval.runner import run_fixture

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main_async(args: argparse.Namespace) -> str:
    if args.fixture == "all":
        fixtures = list(ALL_FIXTURES)
    else:
        fixtures = [get_fixture(args.fixture)]

    results = []
    for fixture in fixtures:
        logger.info("Running fixture %s (%s)", fixture.id, fixture.name)
        result = await run_fixture(fixture, prompt_variant=args.prompt)
        results.append(result)

    return render_matrix(results, prompt_variant=args.prompt)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run debrief LLM eval suite")
    parser.add_argument("--fixture", default="all", help="Fixture id (F1..F5) or 'all'")
    parser.add_argument("--prompt", default="current", help="Prompt variant module name (default: current)")
    parser.add_argument("--save-report", action="store_true", help="Save markdown report to docs/superpowers/eval-runs/")
    args = parser.parse_args()

    output = asyncio.run(main_async(args))
    print(output)

    if args.save_report:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        report_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "superpowers" / "eval-runs"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{timestamp}_{args.prompt}.md"
        report_path.write_text(output)
        print(f"\n✓ Report saved to: {report_path}")


if __name__ == "__main__":
    main()
