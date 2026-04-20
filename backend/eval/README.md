# Debrief LLM Eval Framework

Systematically test that `app.agents.prompts.SYSTEM_PROMPT` produces high-quality coaching debriefs.

## Quick start

```bash
cd backend
ANTHROPIC_API_KEY=sk-... python -m eval.run_eval --save-report
```

Output: a markdown matrix scoring LLM mode vs fallback mode across 5 fixtures on 8 dimensions. Reports saved to `docs/superpowers/eval-runs/<timestamp>_<variant>.md`.

## CLI flags

- `--fixture=F1..F5|all` — which scenarios to run (default: all)
- `--prompt=current|<variant>` — which prompt module (default: current)
- `--save-report` — write markdown report to disk

## Eval dimensions

| Dim | Type | Range | Checks |
|---|---|---|---|
| Specificity | deterministic | 0–3 | Each field has a number |
| No generics | deterministic | 0–3 | Banned phrases absent |
| ACWR band | deterministic | 0–3 | Correct label for input ACWR |
| Nutrition ratio | deterministic | 0–3 | 3:1 if TSS<100, 4:1 otherwise |
| VMM math | deterministic | 0–3 | Within ±3h of formula |
| Actionability | deterministic | 0–3 | Duration + zone + HR cue |
| Coherence | LLM judge | 0–3 | Fields agree internally and with input |
| Coach value | LJM judge | 1.0–5.0 | Would an elite coach sign off? |

## Iteration loop

1. Edit `backend/app/agents/prompts.py`
2. `python -m eval.run_eval --save-report`
3. Open the saved report; inspect any fixture with deterministic dim < 3/3 or coach_value < 3.5
4. The "Raw debrief outputs" section shows exactly what the LLM produced — read it
5. Adjust prompt; repeat

## Pass thresholds

- Deterministic dims (1–6): 3/3 on every fixture
- Coherence: ≥ 2/3 on every fixture
- Coach value: average ≥ 3.5/5 across all fixtures

## Adding a fixture

Edit `backend/eval/fixtures.py`:
1. Define a new `Fixture(id="F6", ..., expected_signals={...})`
2. Append to `ALL_FIXTURES`
3. Run: `pytest tests/test_eval/`

## Adding a prompt variant

1. Create `backend/eval/prompts/<your_variant>.py` exporting `SYSTEM_PROMPT` and `build_debrief_prompt`
2. Run: `python -m eval.run_eval --prompt=<your_variant> --save-report`
3. Diff the saved report against the latest `current` report

## Cost per run

~25 Claude Sonnet 4.6 calls per full run (5 fixtures × (1 LLM debrief + 2 judges × 2 modes)). Estimated: ~$0.10 per run.

## Why two judges instead of one?

Coherence (0–3) is a hard pass/fail check on internal consistency. Coach value (1–5) is a quality grade. Splitting them prevents one signal from drowning the other.

## Why no LLM call in unit tests?

`test_scorer.py` and `test_matrix.py` test pure logic with hardcoded debriefs — no API calls. `test_judge.py` mocks the Anthropic client. Only `python -m eval.run_eval` makes real API calls.
