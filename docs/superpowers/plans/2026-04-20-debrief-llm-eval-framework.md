# Debrief LLM Eval Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic + LLM-as-judge evaluation harness that scores `_llm_debrief` and `fallback_debrief` outputs across 5 fixture scenarios on 8 dimensions, prints a side-by-side comparison matrix, supports prompt variants, and persists timestamped reports — so we can iterate on `prompts.py` with confidence.

**Architecture:** A standalone `backend/eval/` package independent of `backend/app/`. Fixtures define realistic `ActivityInput + AthleteContext` pairs with `expected_signals`. Six pure-Python scorers check determinism rules. Two judge functions call Claude separately with judge-only system prompts. The orchestrator runs both modes per fixture, aggregates scores, and renders a markdown matrix to stdout (and optionally to disk).

**Tech Stack:**
- Python 3.12, pytest, asyncio
- Anthropic SDK (already in `requirements.txt`) — Claude Sonnet 4.6 for both debrief and judge calls
- Existing schema: `app.agents.schema.ActivityInput`, `AthleteContext`, `RaceTargetContext`
- Existing entry points: `app.agents.debrief_graph._llm_debrief`, `fallback_debrief`, `_DEBRIEF_TOOL`

**Iteration loop the framework enables:**
1. Edit `backend/app/agents/prompts.py`
2. Run `python -m eval.run_eval --save-report`
3. Read the matrix; if any deterministic dim < 3/3 or coach_value < 3.5/5, inspect the offending fixture's raw debrief in the saved report
4. Adjust prompt, repeat
5. To A/B test: drop a new file in `backend/eval/prompts/<variant>.py` exporting `SYSTEM_PROMPT` + `build_debrief_prompt`, then run `--prompt=<variant>`

---

## File Structure

| Path | Responsibility |
|---|---|
| `backend/eval/__init__.py` | Package marker |
| `backend/eval/fixtures.py` | 5 named fixtures with `expected_signals` dict |
| `backend/eval/scorer.py` | 6 deterministic scorers + `score_deterministic` aggregator |
| `backend/eval/judge.py` | 2 LLM-as-judge functions (coherence, coach_value) |
| `backend/eval/matrix.py` | `ModeResult`, `FixtureResult` dataclasses + `render_matrix` |
| `backend/eval/runner.py` | Async `run_fixture` orchestrating both modes |
| `backend/eval/run_eval.py` | CLI entry: `--prompt`, `--fixture`, `--save-report` |
| `backend/eval/prompts/__init__.py` | Package marker |
| `backend/eval/prompts/current.py` | Re-exports live `app.agents.prompts` |
| `backend/eval/prompts/no_vmm_projection.py` | Example variant |
| `backend/eval/README.md` | How to run, add fixtures, add variants |
| `backend/tests/test_eval/__init__.py` | Test package marker |
| `backend/tests/test_eval/test_fixtures.py` | Fixtures load and self-consistency check |
| `backend/tests/test_eval/test_scorer.py` | Unit tests for all 6 scorers + aggregator |
| `backend/tests/test_eval/test_judge.py` | Mocked Anthropic client for both judges + runner test |
| `backend/tests/test_eval/test_matrix.py` | Render produces expected markdown |

**Reports saved to:** `docs/superpowers/eval-runs/YYYY-MM-DD_HH-MM_<variant>.md`

---

## Eval Dimensions (locked spec)

| # | Dimension | Type | Range | What's checked |
|---|---|---|---|---|
| 1 | `specificity` | deterministic | 0–3 | Each of 5 fields contains ≥1 digit (3pt for 5/5, 2pt for 4/5, 1pt for 3/5, 0 below) |
| 2 | `no_generics` | deterministic | 0–3 | None of `("great job", "keep it up", "listen to your body")` in any field = 3; any present = 0 |
| 3 | `acwr_band_correct` | deterministic | 0–3 | `load_verdict` mentions the band label matching computed ACWR (or alias) = 3; otherwise 0 |
| 4 | `nutrition_ratio_correct` | deterministic | 0–3 | TSS<100 → expects `3:1`; TSS≥100 → expects `4:1`. Pattern in `nutrition_protocol` = 3; missing = 0 |
| 5 | `vmm_math_plausible` | deterministic | 0–3 | Extract `XhYYm` from `vmm_projection`; compare to formula `(160000 / (threshold_pace × multiplier)) × 60 + 60000` (multiplier 2.4/2.6/2.9/3.2 by CTL); within ±3h=3, ±6h=2, ±10h=1, else 0 |
| 6 | `actionability` | deterministic | 0–3 | `next_session_action` contains: duration regex, zone marker, HR cue → 1 pt each |
| 7 | `coherence` | LLM judge | 0–3 | Claude scores: do all 5 fields reference the same session without contradicting each other or the input? |
| 8 | `coach_value` | LLM judge | 1.0–5.0 | Claude scores: would an elite ultra coach sign off on this? |

**Pass thresholds for the suite:**
- All deterministic dims (1–6): must score `3/3` on every fixture
- `coherence`: ≥ `2/3` on every fixture
- `coach_value`: average ≥ `3.5/5` across all fixtures

---

## Fixture Scenarios (locked)

| ID | Name | TSS / ACWR / CTL / TSB / decoupling / Z3 / weeks_out | Expected signals |
|---|---|---|---|
| `F1` | Easy Z2 base run | 45 / 1.0 / 52 / 0 / 4% / 5% / 24w | acwr_band=green, ratio=3:1 |
| `F2` | Overreach hard session | 110 / 1.4 / 70 / -18 / 7% / 40% / 16w | acwr_band=caution, ratio=4:1, must_flag_junk_miles |
| `F3` | Long mountain decoupling | 165 / 1.1 / 78 / -10 / 35% / 12% / 12w | acwr_band=green, ratio=4:1, must_flag_vert_debt |
| `F4` | Danger zone | 130 / 1.6 / 65 / -32 / 12% / 45% / 8w | acwr_band=injury risk, ratio=4:1, must_recommend_deload |
| `F5` | Underload recovery | 30 / 0.7 / 48 / +15 / 2% / 5% / 20w | acwr_band=underload, ratio=3:1, must_recommend_volume_increase |

---

## Task 1: Set up package skeleton

**Files:**
- Create: `backend/eval/__init__.py`
- Create: `backend/eval/prompts/__init__.py`
- Create: `backend/tests/test_eval/__init__.py`
- Create: `docs/superpowers/eval-runs/` (directory)

- [ ] **Step 1: Create directories and empty package markers**

```bash
mkdir -p backend/eval/prompts backend/tests/test_eval docs/superpowers/eval-runs
touch backend/eval/__init__.py backend/eval/prompts/__init__.py backend/tests/test_eval/__init__.py
```

- [ ] **Step 2: Verify directories exist**

```bash
ls backend/eval backend/eval/prompts backend/tests/test_eval docs/superpowers/eval-runs
```
Expected: all four directories listed; first three contain `__init__.py`.

- [ ] **Step 3: Commit**

```bash
git add backend/eval backend/tests/test_eval docs/superpowers/eval-runs
git commit -m "chore: add eval package skeleton"
```

---

## Task 2: Define fixtures with expected signals

**Files:**
- Create: `backend/eval/fixtures.py`
- Create: `backend/tests/test_eval/test_fixtures.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_eval/test_fixtures.py`:

```python
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
```

- [ ] **Step 2: Run test, expect ImportError**

```bash
cd backend && python -m pytest tests/test_eval/test_fixtures.py -v
```
Expected: `ModuleNotFoundError: No module named 'eval.fixtures'`

- [ ] **Step 3: Implement `backend/eval/fixtures.py`**

```python
from dataclasses import dataclass

from app.agents.schema import ActivityInput, AthleteContext, RaceTargetContext


@dataclass(frozen=True)
class Fixture:
    id: str
    name: str
    activity: ActivityInput
    context: AthleteContext
    expected_signals: dict


def _vmm_target(weeks_out: int, phase: str) -> RaceTargetContext:
    return RaceTargetContext(
        race_name="VMM",
        weeks_out=weeks_out,
        distance_km=160.0,
        goal_time_sec=None,
        training_phase=phase,
    )


F1 = Fixture(
    id="F1",
    name="Easy Z2 base run",
    activity=ActivityInput(
        activity_name="Morning Easy Run",
        duration_sec=3600,
        distance_m=10000,
        sport_type="Run",
        tss=45.0,
        hr_tss=45.0,
        hr_drift_pct=2.0,
        aerobic_decoupling_pct=4.0,
        ngp_sec_km=330,
        zone_distribution={"z1_pct": 30, "z2_pct": 60, "z3_pct": 5, "z4_pct": 0, "z5_pct": 0},
        elevation_gain_m=80.0,
        cadence_avg=178.0,
    ),
    context=AthleteContext(
        lthr=160, threshold_pace_sec_km=270, tss_30d_avg=55.0,
        acwr=1.0, ctl=52.0, atl=52.0, tsb=0.0,
        training_phase="Base", race_target=_vmm_target(24, "Base"),
    ),
    expected_signals={
        "acwr_band": "green",
        "expected_carb_protein_ratio": "3:1",
        "must_flag_junk_miles": False,
        "must_flag_vert_debt": False,
        "must_recommend_deload": False,
        "must_recommend_volume_increase": False,
    },
)

F2 = Fixture(
    id="F2",
    name="Overreach hard session",
    activity=ActivityInput(
        activity_name="Hard Tempo",
        duration_sec=4500,
        distance_m=12500,
        sport_type="Run",
        tss=110.0,
        hr_tss=110.0,
        hr_drift_pct=9.0,
        aerobic_decoupling_pct=7.0,
        ngp_sec_km=265,
        zone_distribution={"z1_pct": 5, "z2_pct": 25, "z3_pct": 40, "z4_pct": 25, "z5_pct": 5},
        elevation_gain_m=120.0,
        cadence_avg=176.0,
    ),
    context=AthleteContext(
        lthr=162, threshold_pace_sec_km=265, tss_30d_avg=78.0,
        acwr=1.4, ctl=70.0, atl=98.0, tsb=-18.0,
        training_phase="Build", race_target=_vmm_target(16, "Build"),
    ),
    expected_signals={
        "acwr_band": "caution",
        "expected_carb_protein_ratio": "4:1",
        "must_flag_junk_miles": True,
        "must_flag_vert_debt": False,
        "must_recommend_deload": False,
        "must_recommend_volume_increase": False,
    },
)

F3 = Fixture(
    id="F3",
    name="Long mountain decoupling",
    activity=ActivityInput(
        activity_name="Long Mountain Run",
        duration_sec=14400,
        distance_m=22000,
        sport_type="TrailRun",
        tss=165.0,
        hr_tss=165.0,
        hr_drift_pct=6.0,
        aerobic_decoupling_pct=35.0,
        ngp_sec_km=480,
        zone_distribution={"z1_pct": 50, "z2_pct": 35, "z3_pct": 12, "z4_pct": 3, "z5_pct": 0},
        elevation_gain_m=800.0,
        cadence_avg=172.0,
    ),
    context=AthleteContext(
        lthr=158, threshold_pace_sec_km=280, tss_30d_avg=95.0,
        acwr=1.1, ctl=78.0, atl=86.0, tsb=-10.0,
        training_phase="Build", race_target=_vmm_target(12, "Peak"),
    ),
    expected_signals={
        "acwr_band": "green",
        "expected_carb_protein_ratio": "4:1",
        "must_flag_junk_miles": False,
        "must_flag_vert_debt": True,
        "must_recommend_deload": False,
        "must_recommend_volume_increase": False,
    },
)

F4 = Fixture(
    id="F4",
    name="Danger zone — overtrained",
    activity=ActivityInput(
        activity_name="Long Tempo",
        duration_sec=5400,
        distance_m=14000,
        sport_type="Run",
        tss=130.0,
        hr_tss=130.0,
        hr_drift_pct=8.5,
        aerobic_decoupling_pct=12.0,
        ngp_sec_km=270,
        zone_distribution={"z1_pct": 10, "z2_pct": 30, "z3_pct": 45, "z4_pct": 12, "z5_pct": 3},
        elevation_gain_m=200.0,
        cadence_avg=174.0,
    ),
    context=AthleteContext(
        lthr=160, threshold_pace_sec_km=270, tss_30d_avg=80.0,
        acwr=1.6, ctl=65.0, atl=104.0, tsb=-32.0,
        training_phase="Peak", race_target=_vmm_target(8, "Peak"),
    ),
    expected_signals={
        "acwr_band": "injury risk",
        "expected_carb_protein_ratio": "4:1",
        "must_flag_junk_miles": False,
        "must_flag_vert_debt": False,
        "must_recommend_deload": True,
        "must_recommend_volume_increase": False,
    },
)

F5 = Fixture(
    id="F5",
    name="Underload recovery week",
    activity=ActivityInput(
        activity_name="Recovery Jog",
        duration_sec=1800,
        distance_m=5000,
        sport_type="Run",
        tss=30.0,
        hr_tss=30.0,
        hr_drift_pct=1.0,
        aerobic_decoupling_pct=2.0,
        ngp_sec_km=360,
        zone_distribution={"z1_pct": 60, "z2_pct": 35, "z3_pct": 5, "z4_pct": 0, "z5_pct": 0},
        elevation_gain_m=50.0,
        cadence_avg=176.0,
    ),
    context=AthleteContext(
        lthr=160, threshold_pace_sec_km=275, tss_30d_avg=70.0,
        acwr=0.7, ctl=48.0, atl=33.0, tsb=15.0,
        training_phase="Base", race_target=_vmm_target(20, "Base"),
    ),
    expected_signals={
        "acwr_band": "underload",
        "expected_carb_protein_ratio": "3:1",
        "must_flag_junk_miles": False,
        "must_flag_vert_debt": False,
        "must_recommend_deload": False,
        "must_recommend_volume_increase": True,
    },
)

ALL_FIXTURES: tuple[Fixture, ...] = (F1, F2, F3, F4, F5)
_BY_ID = {f.id: f for f in ALL_FIXTURES}


def get_fixture(fixture_id: str) -> Fixture:
    return _BY_ID[fixture_id]
```

- [ ] **Step 4: Run test, expect pass**

```bash
cd backend && python -m pytest tests/test_eval/test_fixtures.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/eval/fixtures.py backend/tests/test_eval/test_fixtures.py
git commit -m "feat(eval): add 5 fixture scenarios with expected signals"
```

---

## Task 3: Specificity scorer

**Files:**
- Create: `backend/eval/scorer.py`
- Create: `backend/tests/test_eval/test_scorer.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_eval/test_scorer.py`:

```python
from eval.scorer import score_specificity


def test_specificity_all_fields_have_numbers() -> None:
    debrief = {
        "load_verdict": "TSS 110 over 80 average. ACWR 1.4.",
        "technical_insight": "HR drift 9%. Z3 40%.",
        "next_session_action": "60 min Z2, HR < 150.",
        "nutrition_protocol": "60g carb in 45 min.",
        "vmm_projection": "VMM 30h15m, CTL 70.",
    }
    assert score_specificity(debrief) == 3


def test_specificity_three_fields_missing_numbers() -> None:
    debrief = {
        "load_verdict": "Solid effort today.",
        "technical_insight": "Good aerobic work.",
        "next_session_action": "Recover well.",
        "nutrition_protocol": "60g carb in 45 min.",
        "vmm_projection": "VMM 30h15m.",
    }
    assert score_specificity(debrief) == 0


def test_specificity_one_field_missing_number() -> None:
    debrief = {
        "load_verdict": "TSS 110.",
        "technical_insight": "HR drift 9%.",
        "next_session_action": "Recover well.",
        "nutrition_protocol": "60g carb in 45 min.",
        "vmm_projection": "VMM 30h15m.",
    }
    assert score_specificity(debrief) == 2
```

- [ ] **Step 2: Run, expect ModuleNotFoundError**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```
Expected: `ModuleNotFoundError: No module named 'eval.scorer'`

- [ ] **Step 3: Create `backend/eval/scorer.py`**

```python
"""Deterministic scorers for debrief output. Each returns 0-3."""
import re

_FIELDS = ("load_verdict", "technical_insight", "next_session_action", "nutrition_protocol", "vmm_projection")
_HAS_DIGIT = re.compile(r"\d")


def score_specificity(debrief: dict[str, str]) -> int:
    fields_with_numbers = sum(1 for f in _FIELDS if _HAS_DIGIT.search(debrief.get(f, "")))
    if fields_with_numbers == 5:
        return 3
    if fields_with_numbers == 4:
        return 2
    if fields_with_numbers == 3:
        return 1
    return 0
```

- [ ] **Step 4: Run, expect pass**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/eval/scorer.py backend/tests/test_eval/test_scorer.py
git commit -m "feat(eval): add specificity scorer"
```

---

## Task 4: No-generics scorer

**Files:**
- Modify: `backend/eval/scorer.py`
- Modify: `backend/tests/test_eval/test_scorer.py`

- [ ] **Step 1: Append failing test to `test_scorer.py`**

```python
from eval.scorer import score_no_generics


def test_no_generics_clean_output() -> None:
    debrief = {
        "load_verdict": "TSS 110 over 80 average.",
        "technical_insight": "HR drift 9%.",
        "next_session_action": "60 min Z2.",
        "nutrition_protocol": "60g carb in 45 min.",
        "vmm_projection": "VMM 30h15m.",
    }
    assert score_no_generics(debrief) == 3


def test_no_generics_contains_great_job() -> None:
    debrief = {
        "load_verdict": "Great job today!",
        "technical_insight": "HR drift 9%.",
        "next_session_action": "60 min Z2.",
        "nutrition_protocol": "60g carb.",
        "vmm_projection": "VMM 30h15m.",
    }
    assert score_no_generics(debrief) == 0


def test_no_generics_listen_to_body_anywhere() -> None:
    debrief = {
        "load_verdict": "TSS 110.",
        "technical_insight": "HR drift 9%. Listen to your body next time.",
        "next_session_action": "60 min Z2.",
        "nutrition_protocol": "60g carb.",
        "vmm_projection": "VMM 30h15m.",
    }
    assert score_no_generics(debrief) == 0
```

- [ ] **Step 2: Run, expect 3 new failures**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```
Expected: `ImportError: cannot import name 'score_no_generics'`

- [ ] **Step 3: Append `score_no_generics` to `backend/eval/scorer.py`**

```python
_GENERIC_PHRASES = ("great job", "keep it up", "listen to your body")


def score_no_generics(debrief: dict[str, str]) -> int:
    combined = " ".join(debrief.get(f, "") for f in _FIELDS).lower()
    return 0 if any(phrase in combined for phrase in _GENERIC_PHRASES) else 3
```

- [ ] **Step 4: Run, expect all pass**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```
Expected: 6 passed total.

- [ ] **Step 5: Commit**

```bash
git add backend/eval/scorer.py backend/tests/test_eval/test_scorer.py
git commit -m "feat(eval): add no-generics scorer"
```

---

## Task 5: ACWR band scorer

**Files:**
- Modify: `backend/eval/scorer.py`
- Modify: `backend/tests/test_eval/test_scorer.py`

- [ ] **Step 1: Append failing test**

```python
from eval.scorer import score_acwr_band


def test_acwr_band_correct_green() -> None:
    debrief = {"load_verdict": "ACWR 1.0 → green band. CTL 52.", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_acwr_band(debrief, expected_band="green") == 3


def test_acwr_band_correct_caution() -> None:
    debrief = {"load_verdict": "ACWR 1.4 → caution. Reduce next.", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_acwr_band(debrief, expected_band="caution") == 3


def test_acwr_band_wrong_label() -> None:
    debrief = {"load_verdict": "ACWR 1.4 → green band.", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_acwr_band(debrief, expected_band="caution") == 0


def test_acwr_band_injury_risk_alias() -> None:
    debrief = {"load_verdict": "ACWR 1.6 — danger zone today.", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_acwr_band(debrief, expected_band="injury risk") == 3
```

- [ ] **Step 2: Run, expect 4 new failures**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```

- [ ] **Step 3: Append `score_acwr_band` to `backend/eval/scorer.py`**

```python
_BAND_ALIASES: dict[str, tuple[str, ...]] = {
    "underload": ("underload",),
    "green": ("green", "optimal", "sweet spot"),
    "caution": ("caution", "overreach"),
    "injury risk": ("injury risk", "danger", "danger zone"),
}


def score_acwr_band(debrief: dict[str, str], expected_band: str) -> int:
    text = debrief.get("load_verdict", "").lower()
    aliases = _BAND_ALIASES.get(expected_band, (expected_band,))
    return 3 if any(alias in text for alias in aliases) else 0
```

- [ ] **Step 4: Run, expect pass**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```
Expected: 10 passed total.

- [ ] **Step 5: Commit**

```bash
git add backend/eval/scorer.py backend/tests/test_eval/test_scorer.py
git commit -m "feat(eval): add ACWR band correctness scorer"
```

---

## Task 6: Nutrition ratio scorer

**Files:**
- Modify: `backend/eval/scorer.py`
- Modify: `backend/tests/test_eval/test_scorer.py`

- [ ] **Step 1: Append failing test**

```python
from eval.scorer import score_nutrition_ratio


def test_nutrition_ratio_4to1_for_high_tss() -> None:
    debrief = {"load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "Tỷ lệ 4:1 carb:protein. 80g carb + 20g protein.", "vmm_projection": ""}
    assert score_nutrition_ratio(debrief, tss=120) == 3


def test_nutrition_ratio_3to1_for_low_tss() -> None:
    debrief = {"load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "3:1 ratio: 45g carb + 15g protein.", "vmm_projection": ""}
    assert score_nutrition_ratio(debrief, tss=50) == 3


def test_nutrition_ratio_wrong_for_high_tss() -> None:
    debrief = {"load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "3:1 ratio works fine.", "vmm_projection": ""}
    assert score_nutrition_ratio(debrief, tss=120) == 0


def test_nutrition_ratio_missing_pattern() -> None:
    debrief = {"load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "Eat phở and drink water.", "vmm_projection": ""}
    assert score_nutrition_ratio(debrief, tss=50) == 0
```

- [ ] **Step 2: Run, expect failure**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```

- [ ] **Step 3: Append `score_nutrition_ratio` to `backend/eval/scorer.py`**

```python
def score_nutrition_ratio(debrief: dict[str, str], tss: float) -> int:
    expected = "4:1" if tss >= 100 else "3:1"
    text = debrief.get("nutrition_protocol", "")
    return 3 if expected in text else 0
```

- [ ] **Step 4: Run, expect pass**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```
Expected: 14 passed total.

- [ ] **Step 5: Commit**

```bash
git add backend/eval/scorer.py backend/tests/test_eval/test_scorer.py
git commit -m "feat(eval): add nutrition ratio correctness scorer"
```

---

## Task 7: VMM math plausibility scorer

**Files:**
- Modify: `backend/eval/scorer.py`
- Modify: `backend/tests/test_eval/test_scorer.py`

- [ ] **Step 1: Append failing test**

```python
from eval.scorer import score_vmm_math


def test_vmm_math_within_3h_of_formula() -> None:
    # CTL 70 → multiplier 2.6, threshold_pace 270 sec/km
    # flat = 160000 / (270*2.6) sec * 60 / 60 = ~228 min = 3.8h flat
    # + elevation = (10000/10)*60 = 60000 sec = 16.67h
    # total ≈ 20.4h
    debrief = {"vmm_projection": "VMM 160km projection: 20h30m (trained).", "load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": ""}
    assert score_vmm_math(debrief, ctl=70, threshold_pace_sec_km=270) == 3


def test_vmm_math_within_6h_partial_credit() -> None:
    debrief = {"vmm_projection": "VMM 160km projection: 26h00m.", "load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": ""}
    assert score_vmm_math(debrief, ctl=70, threshold_pace_sec_km=270) == 2


def test_vmm_math_no_time_pattern_zero() -> None:
    debrief = {"vmm_projection": "Insufficient data.", "load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": ""}
    assert score_vmm_math(debrief, ctl=70, threshold_pace_sec_km=270) == 0


def test_vmm_math_extreme_outlier_zero() -> None:
    debrief = {"vmm_projection": "VMM 160km projection: 50h00m.", "load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": ""}
    assert score_vmm_math(debrief, ctl=70, threshold_pace_sec_km=270) == 0
```

- [ ] **Step 2: Run, expect failure**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```

- [ ] **Step 3: Append `score_vmm_math` to `backend/eval/scorer.py`**

```python
_TIME_PATTERN = re.compile(r"(\d+)\s*h\s*(\d+)?\s*m?", re.IGNORECASE)


def _expected_vmm_hours(ctl: float, threshold_pace_sec_km: float) -> float:
    if ctl >= 90:
        multiplier = 2.4
    elif ctl >= 70:
        multiplier = 2.6
    elif ctl >= 50:
        multiplier = 2.9
    else:
        multiplier = 3.2
    flat_sec = 160_000 / (threshold_pace_sec_km * multiplier) * 60
    elevation_sec = (10_000 / 10) * 60
    return (flat_sec + elevation_sec) / 3600


def score_vmm_math(debrief: dict[str, str], ctl: float, threshold_pace_sec_km: float) -> int:
    text = debrief.get("vmm_projection", "")
    match = _TIME_PATTERN.search(text)
    if not match:
        return 0
    hours = int(match.group(1))
    minutes = int(match.group(2)) if match.group(2) else 0
    actual = hours + minutes / 60
    expected = _expected_vmm_hours(ctl, threshold_pace_sec_km)
    delta = abs(actual - expected)
    if delta <= 3:
        return 3
    if delta <= 6:
        return 2
    if delta <= 10:
        return 1
    return 0
```

- [ ] **Step 4: Run, expect pass**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```
Expected: 18 passed total.

- [ ] **Step 5: Commit**

```bash
git add backend/eval/scorer.py backend/tests/test_eval/test_scorer.py
git commit -m "feat(eval): add VMM projection math plausibility scorer"
```

---

## Task 8: Actionability scorer

**Files:**
- Modify: `backend/eval/scorer.py`
- Modify: `backend/tests/test_eval/test_scorer.py`

- [ ] **Step 1: Append failing test**

```python
from eval.scorer import score_actionability


def test_actionability_full_prescription() -> None:
    debrief = {"next_session_action": "Easy 60 min Z2 run, HR cap LTHR-15.", "load_verdict": "", "technical_insight": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_actionability(debrief) == 3


def test_actionability_missing_hr_cue() -> None:
    debrief = {"next_session_action": "Easy 60 min Z2 run.", "load_verdict": "", "technical_insight": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_actionability(debrief) == 2


def test_actionability_only_zone() -> None:
    debrief = {"next_session_action": "Run in Z2.", "load_verdict": "", "technical_insight": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_actionability(debrief) == 1


def test_actionability_vague() -> None:
    debrief = {"next_session_action": "Recover well.", "load_verdict": "", "technical_insight": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_actionability(debrief) == 0


def test_actionability_vietnamese_duration() -> None:
    debrief = {"next_session_action": "Chạy 75 phút Z2, giữ HR dưới LTHR.", "load_verdict": "", "technical_insight": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_actionability(debrief) == 3
```

- [ ] **Step 2: Run, expect failure**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```

- [ ] **Step 3: Append `score_actionability` to `backend/eval/scorer.py`**

```python
_DURATION = re.compile(r"\d+\s*(?:min|phút|h\b)", re.IGNORECASE)
_ZONE = re.compile(r"\bZ[1-5]\b", re.IGNORECASE)
_HR_CUE = re.compile(r"\b(?:HR|LTHR|bpm)\b", re.IGNORECASE)


def score_actionability(debrief: dict[str, str]) -> int:
    text = debrief.get("next_session_action", "")
    points = 0
    if _DURATION.search(text):
        points += 1
    if _ZONE.search(text):
        points += 1
    if _HR_CUE.search(text):
        points += 1
    return points
```

- [ ] **Step 4: Run, expect pass**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```
Expected: 23 passed total.

- [ ] **Step 5: Commit**

```bash
git add backend/eval/scorer.py backend/tests/test_eval/test_scorer.py
git commit -m "feat(eval): add actionability scorer"
```

---

## Task 9: Deterministic eval aggregator

**Files:**
- Modify: `backend/eval/scorer.py`
- Modify: `backend/tests/test_eval/test_scorer.py`

- [ ] **Step 1: Append failing test**

```python
from eval.scorer import DeterministicScores, score_deterministic
from eval.fixtures import F2


def test_score_deterministic_full_pass() -> None:
    debrief = {
        "load_verdict": "TSS 110 over 78 avg. ACWR 1.4 → caution.",
        "technical_insight": "HR drift 9%. Z3 40% — junk miles.",
        "next_session_action": "60 min Z2, HR < LTHR-15.",
        "nutrition_protocol": "TSS 110 = 660 kcal. 4:1 ratio: 80g carb + 20g protein in 30 phút.",
        "vmm_projection": "VMM 160km: 20h30m (trained).",
    }
    scores = score_deterministic(debrief, F2)
    assert isinstance(scores, DeterministicScores)
    assert scores.specificity == 3
    assert scores.no_generics == 3
    assert scores.acwr_band == 3
    assert scores.nutrition_ratio == 3
    assert scores.vmm_math == 3
    assert scores.actionability == 3
    assert scores.total == 18
```

- [ ] **Step 2: Run, expect failure**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```

- [ ] **Step 3: Append `DeterministicScores` + `score_deterministic` to `backend/eval/scorer.py`**

```python
from dataclasses import dataclass

from eval.fixtures import Fixture


@dataclass(frozen=True)
class DeterministicScores:
    specificity: int
    no_generics: int
    acwr_band: int
    nutrition_ratio: int
    vmm_math: int
    actionability: int

    @property
    def total(self) -> int:
        return (
            self.specificity + self.no_generics + self.acwr_band
            + self.nutrition_ratio + self.vmm_math + self.actionability
        )


def score_deterministic(debrief: dict[str, str], fixture: Fixture) -> DeterministicScores:
    return DeterministicScores(
        specificity=score_specificity(debrief),
        no_generics=score_no_generics(debrief),
        acwr_band=score_acwr_band(debrief, fixture.expected_signals["acwr_band"]),
        nutrition_ratio=score_nutrition_ratio(debrief, fixture.activity.tss),
        vmm_math=score_vmm_math(debrief, fixture.context.ctl, fixture.context.threshold_pace_sec_km),
        actionability=score_actionability(debrief),
    )
```

- [ ] **Step 4: Run, expect pass**

```bash
cd backend && python -m pytest tests/test_eval/test_scorer.py -v
```
Expected: 24 passed total.

- [ ] **Step 5: Commit**

```bash
git add backend/eval/scorer.py backend/tests/test_eval/test_scorer.py
git commit -m "feat(eval): add deterministic score aggregator"
```

---

## Task 10: Coherence judge (LLM-as-judge)

**Files:**
- Create: `backend/eval/judge.py`
- Create: `backend/tests/test_eval/test_judge.py`

- [ ] **Step 1: Write the failing test (mocked Claude client)**

Create `backend/tests/test_eval/test_judge.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock

from eval.fixtures import F1
from eval.judge import judge_coherence


def test_judge_coherence_extracts_score_from_tool_use() -> None:
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "submit_coherence_score"
    mock_block.input = {"score": 3, "reasoning": "Fields agree."}

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    debrief = {
        "load_verdict": "TSS 45.",
        "technical_insight": "All metrics nominal.",
        "next_session_action": "60 min Z2.",
        "nutrition_protocol": "3:1 ratio.",
        "vmm_projection": "20h30m.",
    }
    score = asyncio.run(judge_coherence(debrief, F1, client=mock_client))
    assert score == 3
    mock_client.messages.create.assert_awaited_once()


def test_judge_coherence_clamps_invalid_score_to_zero() -> None:
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "submit_coherence_score"
    mock_block.input = {"score": 99, "reasoning": "Invalid."}

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    debrief = {"load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "", "vmm_projection": ""}
    score = asyncio.run(judge_coherence(debrief, F1, client=mock_client))
    assert score == 0
```

- [ ] **Step 2: Run, expect ImportError**

```bash
cd backend && python -m pytest tests/test_eval/test_judge.py -v
```

- [ ] **Step 3: Implement `backend/eval/judge.py`**

```python
"""LLM-as-judge dimensions. Independent Claude calls; never sees which model produced output."""
import logging
from typing import Any

import anthropic

from app.config import settings
from eval.fixtures import Fixture

logger = logging.getLogger(__name__)

_COHERENCE_TOOL: dict[str, Any] = {
    "name": "submit_coherence_score",
    "description": "Score coherence of the debrief against the input data",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 0, "maximum": 3, "description": "0=contradicts, 1=partial, 2=mostly, 3=fully consistent"},
            "reasoning": {"type": "string"},
        },
        "required": ["score", "reasoning"],
    },
}

_COHERENCE_SYSTEM = """\
You are an independent quality auditor. You will see (a) raw activity + athlete state metrics, and (b) a coaching debrief written by an unknown system.
Your only job: do all 5 fields of the debrief reference the SAME session and athlete state? Do they contradict each other or the input data?
Score 0-3:
0 = at least one field contradicts another or the input data
1 = fields are about different sessions (debrief is reused boilerplate)
2 = mostly consistent but at least one field is unrelated to today's session
3 = all 5 fields consistently reference today's session and athlete state
You do not know who wrote the debrief. Do not speculate about the model. Score on coherence only.
"""


async def judge_coherence(
    debrief: dict[str, str],
    fixture: Fixture,
    client: anthropic.AsyncAnthropic | Any | None = None,
) -> int:
    real_client = client or anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_prompt = (
        f"=== INPUT METRICS ===\n"
        f"Activity: {fixture.activity.activity_name} | TSS {fixture.activity.tss} | "
        f"HR drift {fixture.activity.hr_drift_pct}% | decoupling {fixture.activity.aerobic_decoupling_pct}%\n"
        f"Athlete: ACWR {fixture.context.acwr} | CTL {fixture.context.ctl} | TSB {fixture.context.tsb}\n\n"
        f"=== DEBRIEF ===\n"
        f"load_verdict: {debrief.get('load_verdict', '')}\n"
        f"technical_insight: {debrief.get('technical_insight', '')}\n"
        f"next_session_action: {debrief.get('next_session_action', '')}\n"
        f"nutrition_protocol: {debrief.get('nutrition_protocol', '')}\n"
        f"vmm_projection: {debrief.get('vmm_projection', '')}\n\n"
        f"Score the coherence (0-3) and explain in one sentence."
    )
    response = await real_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=_COHERENCE_SYSTEM,
        tools=[_COHERENCE_TOOL],
        tool_choice={"type": "tool", "name": "submit_coherence_score"},
        messages=[{"role": "user", "content": user_prompt}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_coherence_score":
            score = block.input.get("score", 0)
            return score if 0 <= score <= 3 else 0
    return 0
```

- [ ] **Step 4: Run, expect pass**

```bash
cd backend && python -m pytest tests/test_eval/test_judge.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/eval/judge.py backend/tests/test_eval/test_judge.py
git commit -m "feat(eval): add coherence LLM-as-judge"
```

---

## Task 11: Coach value judge (LLM-as-judge)

**Files:**
- Modify: `backend/eval/judge.py`
- Modify: `backend/tests/test_eval/test_judge.py`

- [ ] **Step 1: Append failing test**

```python
from eval.judge import judge_coach_value


def test_judge_coach_value_extracts_float_score() -> None:
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "submit_coach_value_score"
    mock_block.input = {"score": 4.2, "reasoning": "Specific numbers, actionable."}

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    debrief = {"load_verdict": "TSS 45.", "technical_insight": "All nominal.", "next_session_action": "60 min Z2.", "nutrition_protocol": "3:1.", "vmm_projection": "20h30m."}
    score = asyncio.run(judge_coach_value(debrief, F1, client=mock_client))
    assert 4.0 <= score <= 4.5


def test_judge_coach_value_clamps_out_of_range() -> None:
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "submit_coach_value_score"
    mock_block.input = {"score": 99.0, "reasoning": ""}

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    debrief = {"load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "", "vmm_projection": ""}
    score = asyncio.run(judge_coach_value(debrief, F1, client=mock_client))
    assert score == 1.0
```

- [ ] **Step 2: Run, expect failure**

```bash
cd backend && python -m pytest tests/test_eval/test_judge.py -v
```

- [ ] **Step 3: Append to `backend/eval/judge.py`**

```python
_COACH_VALUE_TOOL: dict[str, Any] = {
    "name": "submit_coach_value_score",
    "description": "Score whether an elite coach would sign off on this debrief",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "number", "minimum": 1.0, "maximum": 5.0, "description": "1=harmful or generic, 3=acceptable, 5=elite-coach quality"},
            "reasoning": {"type": "string"},
        },
        "required": ["score", "reasoning"],
    },
}

_COACH_VALUE_SYSTEM = """\
You are an elite ultra-trail coach with 20 years of VMM/UTMB athlete experience.
Score the debrief 1.0-5.0:
1.0 = harmful, generic, or wrong (would mislead an athlete)
2.0 = vague, missing specifics, would not help an athlete improve
3.0 = acceptable — names the issue but actions are too generic
4.0 = good — specific numbers, actionable next session, correct physiology
5.0 = elite — would sign off as if you wrote it yourself; numbers, technical insight, race-specific
Score on quality only. You do not know who wrote it. Be strict; 5.0 is rare.
"""


async def judge_coach_value(
    debrief: dict[str, str],
    fixture: Fixture,
    client: anthropic.AsyncAnthropic | Any | None = None,
) -> float:
    real_client = client or anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_prompt = (
        f"=== ATHLETE PROFILE ===\n"
        f"Race: {fixture.context.race_target.race_name if fixture.context.race_target else 'none'} "
        f"({fixture.context.race_target.weeks_out if fixture.context.race_target else 0}w out)\n"
        f"Phase: {fixture.context.training_phase}\n"
        f"CTL {fixture.context.ctl} / ATL {fixture.context.atl} / TSB {fixture.context.tsb} / ACWR {fixture.context.acwr}\n\n"
        f"=== TODAY'S SESSION ===\n"
        f"{fixture.activity.activity_name}: TSS {fixture.activity.tss}, "
        f"HR drift {fixture.activity.hr_drift_pct}%, decoupling {fixture.activity.aerobic_decoupling_pct}%, "
        f"+{fixture.activity.elevation_gain_m}m D+\n\n"
        f"=== DEBRIEF TO SCORE ===\n"
        f"load_verdict: {debrief.get('load_verdict', '')}\n"
        f"technical_insight: {debrief.get('technical_insight', '')}\n"
        f"next_session_action: {debrief.get('next_session_action', '')}\n"
        f"nutrition_protocol: {debrief.get('nutrition_protocol', '')}\n"
        f"vmm_projection: {debrief.get('vmm_projection', '')}\n\n"
        f"Score 1.0-5.0 and explain."
    )
    response = await real_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=_COACH_VALUE_SYSTEM,
        tools=[_COACH_VALUE_TOOL],
        tool_choice={"type": "tool", "name": "submit_coach_value_score"},
        messages=[{"role": "user", "content": user_prompt}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_coach_value_score":
            score = float(block.input.get("score", 1.0))
            if score < 1.0 or score > 5.0:
                return 1.0
            return score
    return 1.0
```

- [ ] **Step 4: Run, expect pass**

```bash
cd backend && python -m pytest tests/test_eval/test_judge.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/eval/judge.py backend/tests/test_eval/test_judge.py
git commit -m "feat(eval): add coach-value LLM-as-judge"
```

---

## Task 12: Matrix renderer

**Files:**
- Create: `backend/eval/matrix.py`
- Create: `backend/tests/test_eval/test_matrix.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_eval/test_matrix.py`:

```python
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
```

- [ ] **Step 2: Run, expect ImportError**

```bash
cd backend && python -m pytest tests/test_eval/test_matrix.py -v
```

- [ ] **Step 3: Implement `backend/eval/matrix.py`**

```python
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
```

- [ ] **Step 4: Run, expect pass**

```bash
cd backend && python -m pytest tests/test_eval/test_matrix.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/eval/matrix.py backend/tests/test_eval/test_matrix.py
git commit -m "feat(eval): add matrix renderer with per-fixture and average scores"
```

---

## Task 13: Async runner orchestrating one fixture × both modes

**Files:**
- Create: `backend/eval/runner.py`
- Modify: `backend/tests/test_eval/test_judge.py` (extend with runner test)

- [ ] **Step 1: Append failing test to `test_judge.py`**

```python
from unittest.mock import patch

from eval.runner import run_fixture
from eval.matrix import FixtureResult


def test_run_fixture_returns_both_modes() -> None:
    fake_llm_debrief = {
        "load_verdict": "TSS 45 over 55 average. ACWR 1.0 → green.",
        "technical_insight": "All metrics nominal.",
        "next_session_action": "60 min Z2 run, HR cap LTHR-15 bpm.",
        "nutrition_protocol": "3:1 ratio: 45g carb + 15g protein in 45 phút.",
        "vmm_projection": "VMM 160km projection: 22h30m.",
    }

    async def fake_llm(*args, **kwargs):
        return fake_llm_debrief

    async def fake_judge_coh(*args, **kwargs):
        return 3

    async def fake_judge_cv(*args, **kwargs):
        return 4.0

    with (
        patch("eval.runner._call_llm_debrief", side_effect=fake_llm),
        patch("eval.runner.judge_coherence", side_effect=fake_judge_coh),
        patch("eval.runner.judge_coach_value", side_effect=fake_judge_cv),
    ):
        result = asyncio.run(run_fixture(F1, prompt_variant="current"))

    assert isinstance(result, FixtureResult)
    assert result.fixture_id == "F1"
    assert result.llm.coherence == 3
    assert result.llm.coach_value == 4.0
    assert result.fallback.deterministic.specificity > 0
```

- [ ] **Step 2: Run, expect ImportError**

```bash
cd backend && python -m pytest tests/test_eval/test_judge.py -v
```

- [ ] **Step 3: Implement `backend/eval/runner.py`**

```python
"""Orchestrates one fixture × both modes (LLM + fallback) and scores both."""
import importlib
import logging
from typing import Any

import anthropic

from app.agents.debrief_graph import _DEBRIEF_TOOL, fallback_debrief
from app.config import settings
from eval.fixtures import Fixture
from eval.judge import judge_coach_value, judge_coherence
from eval.matrix import FixtureResult, ModeResult
from eval.scorer import score_deterministic

logger = logging.getLogger(__name__)


def _load_prompt_variant(variant: str) -> tuple[str, Any]:
    """Returns (SYSTEM_PROMPT, build_debrief_prompt) from named variant module."""
    if variant == "current":
        from app.agents.prompts import SYSTEM_PROMPT, build_debrief_prompt
        return SYSTEM_PROMPT, build_debrief_prompt
    module = importlib.import_module(f"eval.prompts.{variant}")
    return module.SYSTEM_PROMPT, module.build_debrief_prompt


async def _call_llm_debrief(
    fixture: Fixture, system_prompt: str, build_prompt: Any
) -> dict[str, str]:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_prompt = build_prompt(fixture.activity.model_dump(), fixture.context.model_dump())
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=system_prompt,
        tools=[_DEBRIEF_TOOL],
        tool_choice={"type": "tool", "name": "submit_debrief"},
        messages=[{"role": "user", "content": user_prompt}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_debrief":
            return block.input
    raise RuntimeError("LLM did not return submit_debrief tool use")


async def _score_mode(
    debrief: dict[str, str], fixture: Fixture, mode_label: str
) -> ModeResult:
    deterministic = score_deterministic(debrief, fixture)
    coherence = await judge_coherence(debrief, fixture)
    coach_value = await judge_coach_value(debrief, fixture)
    return ModeResult(
        mode=mode_label,
        deterministic=deterministic,
        coherence=coherence,
        coach_value=coach_value,
        debrief=debrief,
    )


async def run_fixture(fixture: Fixture, prompt_variant: str) -> FixtureResult:
    system_prompt, build_prompt = _load_prompt_variant(prompt_variant)

    try:
        llm_debrief = await _call_llm_debrief(fixture, system_prompt, build_prompt)
    except Exception:
        logger.exception("LLM debrief failed for fixture %s; using empty placeholder", fixture.id)
        llm_debrief = {k: "" for k in ("load_verdict", "technical_insight", "next_session_action", "nutrition_protocol", "vmm_projection")}

    fb_debrief = fallback_debrief(fixture.activity, fixture.context).model_dump()

    llm_result = await _score_mode(llm_debrief, fixture, "LLM")
    fb_result = await _score_mode(fb_debrief, fixture, "Fallback")

    return FixtureResult(
        fixture_id=fixture.id,
        fixture_name=fixture.name,
        llm=llm_result,
        fallback=fb_result,
    )
```

- [ ] **Step 4: Run, expect pass**

```bash
cd backend && python -m pytest tests/test_eval/test_judge.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/eval/runner.py backend/tests/test_eval/test_judge.py
git commit -m "feat(eval): add async runner orchestrating LLM + fallback per fixture"
```

---

## Task 14: CLI entry point

**Files:**
- Create: `backend/eval/run_eval.py`

- [ ] **Step 1: Implement `backend/eval/run_eval.py`**

```python
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
```

- [ ] **Step 2: Verify CLI parses with `--help`**

```bash
cd backend && python -m eval.run_eval --help
```
Expected: usage block listing `--fixture`, `--prompt`, `--save-report`.

- [ ] **Step 3: Smoke-test single fixture (needs ANTHROPIC_API_KEY)**

```bash
cd backend && ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY python -m eval.run_eval --fixture=F1
```
Expected: markdown table printed within ~30 seconds. If API key missing, LLM column will be all zeros (acceptable) and only fallback has real numbers.

- [ ] **Step 4: Commit**

```bash
git add backend/eval/run_eval.py
git commit -m "feat(eval): add CLI entry point with fixture/prompt/save-report flags"
```

---

## Task 15: Add prompt variant directory

**Files:**
- Create: `backend/eval/prompts/current.py`
- Create: `backend/eval/prompts/no_vmm_projection.py` (example variant)

- [ ] **Step 1: Create `backend/eval/prompts/current.py`**

```python
"""Default variant: re-exports the live production prompt."""
from app.agents.prompts import SYSTEM_PROMPT, build_debrief_prompt

__all__ = ["SYSTEM_PROMPT", "build_debrief_prompt"]
```

- [ ] **Step 2: Create example variant `backend/eval/prompts/no_vmm_projection.py`**

```python
"""Variant: drops the VMM projection requirement to measure its impact."""
from app.agents.prompts import build_debrief_prompt

SYSTEM_PROMPT = """\
You are an elite ultra-trail coach. Be specific. Use numbers. Never say "great job", "keep it up", or "listen to your body".

Return exactly 5 fields via the submit_debrief tool:
1. load_verdict: TSS vs 30-day avg, ACWR band, CTL/TSB
2. technical_insight: 1-2 actionable issues with metric values
3. next_session_action: exact next workout (duration, zone, HR ceiling)
4. nutrition_protocol: timing + carb:protein grams + Vietnamese food option
5. vmm_projection: leave empty string ""
"""

__all__ = ["SYSTEM_PROMPT", "build_debrief_prompt"]
```

- [ ] **Step 3: Verify variant mechanism loads**

```bash
cd backend && python -c "from eval.runner import _load_prompt_variant; sp, _ = _load_prompt_variant('no_vmm_projection'); print('loaded:', len(sp), 'chars')"
```
Expected: `loaded: <some-number> chars`

- [ ] **Step 4: Commit**

```bash
git add backend/eval/prompts/
git commit -m "feat(eval): add prompt variant loader with current and no_vmm_projection"
```

---

## Task 16: README and end-to-end sanity check

**Files:**
- Create: `backend/eval/README.md`

- [ ] **Step 1: Write the README**

````markdown
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
| Coach value | LLM judge | 1.0–5.0 | Would an elite coach sign off? |

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
````

- [ ] **Step 2: Run full unit test suite to confirm no regressions**

```bash
cd backend && python -m pytest tests/test_eval/ -v
```
Expected: ~35 tests pass (24 scorer + 4 fixtures + 5 judge + 2 matrix).

- [ ] **Step 3: End-to-end smoke with real Claude API (single fixture)**

```bash
cd backend && ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY python -m eval.run_eval --fixture=F2 --save-report
```
Expected: report saved to `docs/superpowers/eval-runs/<timestamp>_current.md`. Open it and verify:
- LLM column has non-zero scores
- Fallback column has non-zero scores
- "Raw debrief outputs" shows real text from both modes

- [ ] **Step 4: Commit**

```bash
git add backend/eval/README.md
git commit -m "docs(eval): add eval framework README"
```

---

## Self-Review

**Spec coverage:**
- ✓ 6 deterministic scorers — Tasks 3–8 + aggregator in Task 9
- ✓ 2 LLM-as-judge dimensions — Tasks 10 + 11
- ✓ Comparison matrix LLM vs fallback — Tasks 12 + 13
- ✓ 5 fixture scenarios — Task 2
- ✓ Prompt variant support — Task 15 + variant loader in Task 13
- ✓ Persistence — Task 14 `--save-report`
- ✓ Iteration loop docs — Task 16 README
- ✓ TDD throughout — every code task ends with tests passing before commit

**Type consistency:**
- ✓ `Fixture` defined Task 2, used in Tasks 9, 10, 11, 13
- ✓ `DeterministicScores` defined Task 9, used in Tasks 12, 13
- ✓ `ModeResult` and `FixtureResult` defined Task 12, used in Task 13
- ✓ `_DEBRIEF_TOOL` reused from `app.agents.debrief_graph` (single source of truth)

**Placeholder scan:**
- ✓ No "TBD" / "implement later" / "similar to Task N"
- ✓ Every step has either exact code or shell commands with expected output
- ✓ All file paths absolute under `backend/` repository structure

**Granularity:**
- ✓ Each task = ~5 steps; each step = 2–5 minutes
- ✓ TDD pattern every task: test → fail → implement → pass → commit

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-20-debrief-llm-eval-framework.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task with two-stage review. Best for this plan because each task is small and easy to review independently.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
