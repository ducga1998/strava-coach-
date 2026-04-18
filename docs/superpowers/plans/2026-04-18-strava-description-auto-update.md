# Strava Activity Description Auto-Update — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After every activity is ingested, push a compact 4-line coaching block (TSS · ACWR · Z2 · HR drift · next-session instruction) to the Strava activity description, with a deep-dive link back to the coaching app.

**Architecture:** Python assembles the compact block from already-computed metrics; the LLM only contributes the `next_session_action` one-liner and prose debrief. A new `_push_description()` step fires at the end of `_fetch_store_process()`, after the debrief is committed, and swallows all errors so ingestion is never blocked. The VMM directive is injected into the LLM context when `race_target.distance_km >= 80` or name contains "vmm".

**Tech Stack:** FastAPI, SQLAlchemy 2 async, httpx, langchain-anthropic 0.3, pytest-asyncio 0.24, SQLite in-memory (tests)

---

## File Map

| Action | File |
|---|---|
| Modify | `backend/app/config.py` |
| Modify | `backend/app/agents/schema.py` |
| **Create** | `backend/app/services/description_builder.py` |
| Modify | `backend/app/services/strava_client.py` |
| Modify | `backend/app/agents/debrief_graph.py` |
| Modify | `backend/app/services/activity_ingestion.py` |
| **Create** | `backend/tests/test_services/__init__.py` |
| **Create** | `backend/tests/test_services/test_description_builder.py` |
| **Create** | `backend/tests/test_services/test_activity_ingestion.py` |
| Modify | `backend/tests/test_agents/test_debrief_graph.py` |

---

## Task 1: Add `STRAVA_PUSH_DESCRIPTION` feature flag to config

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add the field to `Settings`**

Open `backend/app/config.py`. Add one line inside `Settings`:

```python
strava_push_description: bool = False
```

Full updated `Settings` block:
```python
class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/stravacoach"
    redis_url: str = "redis://localhost:6379/0"
    strava_client_id: str = "test-client-id"
    strava_client_secret: str = "test-client-secret"
    strava_verify_token: str = "test-verify-token"
    strava_webhook_callback_url: str = "http://localhost:8000/webhook/strava"
    strava_auth_callback_url: str = "http://localhost:8000/auth/callback"
    encryption_key: str = Field(
        default="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
    )
    anthropic_api_key: str = ""
    jwt_secret: str = "test-jwt-secret"
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = ""
    enable_llm_debriefs: bool = False
    strava_push_description: bool = False          # ← NEW
```

- [ ] **Step 2: Run existing tests to confirm no regression**

```bash
cd backend
~/.pyenv/versions/3.13.9/bin/python -m pytest tests/ -q
```

Expected: `29 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add STRAVA_PUSH_DESCRIPTION feature flag to config"
```

---

## Task 2: Extend schema — add `RaceTargetContext`, update `AthleteContext`

**Files:**
- Modify: `backend/app/agents/schema.py`

- [ ] **Step 1: Replace the file contents**

```python
# backend/app/agents/schema.py
from pydantic import BaseModel, Field


class ActivityInput(BaseModel):
    activity_name: str
    duration_sec: int
    distance_m: float
    sport_type: str
    tss: float
    hr_tss: float
    hr_drift_pct: float
    aerobic_decoupling_pct: float
    ngp_sec_km: float
    zone_distribution: dict[str, float]


class RaceTargetContext(BaseModel):
    race_name: str
    weeks_out: int
    distance_km: float
    goal_time_sec: int | None = None
    training_phase: str  # Base / Build / Peak / Taper


class AthleteContext(BaseModel):
    lthr: int
    threshold_pace_sec_km: int
    tss_30d_avg: float
    acwr: float
    ctl: float
    atl: float
    tsb: float
    training_phase: str
    race_target: RaceTargetContext | None = None  # None when no A-race configured


class DebriefOutput(BaseModel):
    load_verdict: str = Field(max_length=400)
    technical_insight: str = Field(max_length=400)
    next_session_action: str = Field(max_length=400)
```

- [ ] **Step 2: Run existing tests — `race_target` defaults to `None`, existing `sample_context()` still valid**

```bash
~/.pyenv/versions/3.13.9/bin/python -m pytest tests/test_agents/ -v
```

Expected: `1 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/schema.py
git commit -m "feat: add RaceTargetContext to AthleteContext schema"
```

---

## Task 3: Create `description_builder.py` with pure formatting functions

**Files:**
- Create: `backend/app/services/description_builder.py`
- Create: `backend/tests/test_services/__init__.py`
- Create: `backend/tests/test_services/test_description_builder.py`

- [ ] **Step 1: Write the failing tests first**

```bash
mkdir -p backend/tests/test_services
touch backend/tests/test_services/__init__.py
```

Create `backend/tests/test_services/test_description_builder.py`:

```python
from app.services.description_builder import acwr_zone_label, format_strava_description


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
```

- [ ] **Step 2: Run tests — confirm they all FAIL (module not found)**

```bash
~/.pyenv/versions/3.13.9/bin/python -m pytest tests/test_services/test_description_builder.py -v
```

Expected: `ERROR — ModuleNotFoundError: No module named 'app.services.description_builder'`

- [ ] **Step 3: Implement `description_builder.py`**

Create `backend/app/services/description_builder.py`:

```python
def acwr_zone_label(acwr: float) -> str:
    if acwr < 0.8:
        return "underload"
    if acwr <= 1.3:
        return "green"
    if acwr <= 1.5:
        return "caution"
    return "injury risk"


def format_strava_description(
    tss: float,
    acwr: float,
    z2_pct: float,
    hr_drift_pct: float,
    decoupling_pct: float,
    next_action: str,
    deep_dive_url: str,
) -> str:
    zone = acwr_zone_label(acwr)
    return (
        f"⚡ TSS {tss:.0f} · ACWR {acwr:.2f} ({zone}) · Z2 {z2_pct:.0f}%\n"
        f"📉 HR drift {hr_drift_pct:.1f}% · decoupling {decoupling_pct:.1f}%\n"
        f"→ {next_action}\n"
        f"🔍 {deep_dive_url}"
    )
```

- [ ] **Step 4: Run tests — confirm all pass**

```bash
~/.pyenv/versions/3.13.9/bin/python -m pytest tests/test_services/test_description_builder.py -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/description_builder.py \
        backend/tests/test_services/__init__.py \
        backend/tests/test_services/test_description_builder.py
git commit -m "feat: add description_builder pure formatting functions"
```

---

## Task 4: Add `update_activity_description` to Strava client

**Files:**
- Modify: `backend/app/services/strava_client.py`

- [ ] **Step 1: Add method to `StravaClientProtocol`**

In `StravaClientProtocol`, after `get_activity_streams`:

```python
async def update_activity_description(
    self, access_token: str, strava_activity_id: int, description: str
) -> None:
    raise NotImplementedError
```

- [ ] **Step 2: Add method to `StravaClient`**

In `StravaClient`, after `get_activity_streams`:

```python
async def update_activity_description(
    self, access_token: str, strava_activity_id: int, description: str
) -> None:
    await self._request(
        "PUT",
        f"{STRAVA_BASE_URL}/activities/{strava_activity_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"description": description},
    )
```

- [ ] **Step 3: Run full test suite — confirm no regression**

```bash
~/.pyenv/versions/3.13.9/bin/python -m pytest tests/ -q
```

Expected: `37 passed` (29 original + 8 from Task 3)

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/strava_client.py
git commit -m "feat: add update_activity_description to StravaClient"
```

---

## Task 5: Update `debrief_graph.py` — race-target-aware advice + VMM directive

**Files:**
- Modify: `backend/app/agents/debrief_graph.py`
- Modify: `backend/tests/test_agents/test_debrief_graph.py`

- [ ] **Step 1: Write new failing tests**

Add to `backend/tests/test_agents/test_debrief_graph.py`:

```python
from app.agents.schema import RaceTargetContext
from app.agents.debrief_graph import next_session_action, _is_ultra_target


def test_next_session_action_no_target_recovery() -> None:
    result = next_session_action(acwr=1.6, tsb=-35.0, target=None)
    assert "Recovery" in result
    assert "Z1" in result or "Z1-Z2" in result


def test_next_session_action_no_target_underload() -> None:
    result = next_session_action(acwr=0.7, tsb=5.0, target=None)
    assert "Z2" in result
    assert "strides" in result.lower() or "aerobic" in result.lower()


def test_next_session_action_prepends_race_name() -> None:
    target = RaceTargetContext(
        race_name="UTMB", weeks_out=10, distance_km=171.0, training_phase="Build"
    )
    result = next_session_action(acwr=1.1, tsb=-5.0, target=target)
    assert result.startswith("UTMB 10w:")


def test_next_session_action_vmm_ultra_build_adds_descent_cue() -> None:
    target = RaceTargetContext(
        race_name="VMM", weeks_out=8, distance_km=160.0, training_phase="Build"
    )
    result = next_session_action(acwr=1.1, tsb=2.0, target=target)
    assert "VMM 8w:" in result
    assert "downhill" in result.lower() or "descent" in result.lower() or ">15%" in result


def test_next_session_action_vmm_no_descent_when_fatigued() -> None:
    target = RaceTargetContext(
        race_name="VMM", weeks_out=8, distance_km=160.0, training_phase="Build"
    )
    # TSB < -10 → skip VMM descent directive, use recovery base
    result = next_session_action(acwr=1.6, tsb=-35.0, target=target)
    assert "VMM 8w:" in result
    assert "Recovery" in result


def test_is_ultra_target_by_distance() -> None:
    target = RaceTargetContext(
        race_name="Some Race", weeks_out=10, distance_km=100.0, training_phase="Build"
    )
    assert _is_ultra_target(target) is True


def test_is_ultra_target_by_name() -> None:
    target = RaceTargetContext(
        race_name="VMM 80km", weeks_out=10, distance_km=50.0, training_phase="Build"
    )
    assert _is_ultra_target(target) is True


def test_is_ultra_target_false_for_marathon() -> None:
    target = RaceTargetContext(
        race_name="Paris Marathon", weeks_out=10, distance_km=42.2, training_phase="Build"
    )
    assert _is_ultra_target(target) is False
```

- [ ] **Step 2: Run new tests — confirm they FAIL**

```bash
~/.pyenv/versions/3.13.9/bin/python -m pytest tests/test_agents/ -v
```

Expected: `1 passed, 8 failed` (the 8 new tests fail)

- [ ] **Step 3: Rewrite `debrief_graph.py`**

```python
# backend/app/agents/debrief_graph.py
from app.agents.schema import ActivityInput, AthleteContext, DebriefOutput, RaceTargetContext
from app.services.description_builder import acwr_zone_label

GENERIC_PHRASES = ("great job", "keep it up", "listen to your body")


async def generate_debrief(
    activity: ActivityInput, context: AthleteContext
) -> dict[str, str]:
    return fallback_debrief(activity, context).model_dump()


def fallback_debrief(
    activity: ActivityInput, context: AthleteContext
) -> DebriefOutput:
    tss_pct = percent_of_average(activity.tss, context.tss_30d_avg)
    zone = acwr_zone_label(context.acwr)
    return DebriefOutput(
        load_verdict=(
            f"TSS {activity.tss:.0f} is {tss_pct:.0f}% of 30-day average; "
            f"ACWR {context.acwr:.2f} is {zone}."
        ),
        technical_insight=(
            f"HR drift {activity.hr_drift_pct:.1f}% and decoupling "
            f"{activity.aerobic_decoupling_pct:.1f}% with "
            f"Z2 {activity.zone_distribution.get('z2_pct', 0.0):.0f}%."
        ),
        next_session_action=next_session_action(
            context.acwr, context.tsb, context.race_target
        ),
    )


def next_session_action(
    acwr: float, tsb: float, target: RaceTargetContext | None
) -> str:
    if acwr > 1.5 or tsb < -30:
        base = "Recovery run 40-50 min in Z1-Z2, HR below LTHR minus 30 bpm."
    elif acwr < 0.8:
        base = "Aerobic endurance run 75-90 min in Z2 with 6 x 20 sec strides."
    else:
        base = "Easy trail run 60 min in Z2, keep climbs below threshold effort."

    if target is None:
        return base

    prefix = f"{target.race_name} {target.weeks_out}w: "
    if _is_ultra_target(target) and tsb > -10 and target.training_phase in ("Build", "Peak"):
        return f"{prefix}90' trail, downhill tech >15% slope, quad-load descents."
    return f"{prefix}{base}"


def _is_ultra_target(target: RaceTargetContext) -> bool:
    return "vmm" in target.race_name.lower() or target.distance_km >= 80


def percent_of_average(value: float, average: float) -> float:
    if average <= 0:
        return 0.0
    return value / average * 100.0
```

- [ ] **Step 4: Run all agent tests**

```bash
~/.pyenv/versions/3.13.9/bin/python -m pytest tests/test_agents/ -v
```

Expected: `9 passed`

- [ ] **Step 5: Run full suite**

```bash
~/.pyenv/versions/3.13.9/bin/python -m pytest tests/ -q
```

Expected: `46 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/debrief_graph.py backend/tests/test_agents/test_debrief_graph.py
git commit -m "feat: VMM-aware next_session_action with race target context"
```

---

## Task 6: Update `activity_ingestion.py` — real athlete context + `_push_description`

**Files:**
- Modify: `backend/app/services/activity_ingestion.py`
- Create: `backend/tests/test_services/test_activity_ingestion.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_services/test_activity_ingestion.py`.

These tests use `asyncio.run()` with fully mocked sessions to avoid event-loop conflicts with the `db_session` fixture:

```python
import asyncio
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.activity_ingestion import _push_description


def _mock_activity(debrief: dict | None = None, *, strava_id: int = 12345) -> MagicMock:
    activity = MagicMock()
    activity.id = 1
    activity.strava_activity_id = strava_id
    activity.athlete_id = 1
    activity.debrief = debrief
    return activity


def _mock_metrics(
    hr_tss: float = 72.0,
    hr_drift_pct: float = 4.1,
    decoupling_pct: float = 3.8,
    z2_pct: float = 68.0,
) -> MagicMock:
    m = MagicMock()
    m.hr_tss = hr_tss
    m.hr_drift_pct = hr_drift_pct
    m.aerobic_decoupling_pct = decoupling_pct
    m.zone_distribution = {"z2_pct": z2_pct}
    return m


def _mock_session(metrics: MagicMock | None, load: MagicMock | None = None) -> AsyncMock:
    session = AsyncMock()
    results = []
    for val in [metrics, load]:
        r = MagicMock()
        r.scalar_one_or_none.return_value = val
        results.append(r)
    session.execute.side_effect = results
    return session


def test_push_description_skipped_when_flag_off() -> None:
    async def run() -> None:
        activity = _mock_activity(debrief={"next_session_action": "Easy run"})
        mock_client = AsyncMock()
        with patch("app.services.activity_ingestion.settings") as s:
            s.strava_push_description = False
            s.frontend_url = "http://localhost:5173"
            await _push_description(AsyncMock(), activity, mock_client, "tok")
        mock_client.update_activity_description.assert_not_called()

    asyncio.run(run())


def test_push_description_skipped_when_no_debrief() -> None:
    async def run() -> None:
        activity = _mock_activity(debrief=None)
        mock_client = AsyncMock()
        with patch("app.services.activity_ingestion.settings") as s:
            s.strava_push_description = True
            s.frontend_url = "http://localhost:5173"
            await _push_description(AsyncMock(), activity, mock_client, "tok")
        mock_client.update_activity_description.assert_not_called()

    asyncio.run(run())


def test_push_description_calls_client_with_formatted_text() -> None:
    async def run() -> None:
        activity = _mock_activity(debrief={"next_session_action": "VMM 8w: easy trail"})
        session = _mock_session(metrics=_mock_metrics(), load=None)
        mock_client = AsyncMock()
        with patch("app.services.activity_ingestion.settings") as s:
            s.strava_push_description = True
            s.frontend_url = "http://localhost:5173"
            await _push_description(session, activity, mock_client, "tok")
        mock_client.update_activity_description.assert_called_once()
        _, _, _, description = mock_client.update_activity_description.call_args[0]
        assert "TSS 72" in description
        assert "VMM 8w: easy trail" in description
        assert "http://localhost:5173/activities/1" in description

    asyncio.run(run())


def test_push_description_swallows_http_error() -> None:
    async def run() -> None:
        activity = _mock_activity(debrief={"next_session_action": "Easy Z2"})
        session = _mock_session(metrics=_mock_metrics(), load=None)
        mock_client = AsyncMock()
        mock_client.update_activity_description.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=MagicMock(status_code=403)
        )
        with patch("app.services.activity_ingestion.settings") as s:
            s.strava_push_description = True
            s.frontend_url = "http://localhost:5173"
            await _push_description(session, activity, mock_client, "tok")  # must not raise
        mock_client.update_activity_description.assert_called_once()

    asyncio.run(run())
```

- [ ] **Step 2: Run new tests — confirm they FAIL**

```bash
~/.pyenv/versions/3.13.9/bin/python -m pytest tests/test_services/test_activity_ingestion.py -v
```

Expected: 4 failures (ImportError — `_push_description` not yet importable)

- [ ] **Step 3: Update imports at the top of `activity_ingestion.py`**

Replace the import block:

```python
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.debrief_graph import generate_debrief
from app.agents.schema import ActivityInput, AthleteContext, RaceTargetContext
from app.config import settings
from app.metrics.engine import compute_activity_metrics
from app.models.activity import Activity
from app.models.athlete import Athlete, AthleteProfile
from app.models.credentials import StravaCredential
from app.models.metrics import ActivityMetrics, LoadHistory
from app.models.target import Priority, RaceTarget
from app.services.description_builder import format_strava_description
from app.services.strava_client import StravaClientProtocol, StravaStreamPayload
from app.services.strava_client import StravaActivityPayload
from app.services.token_service import TokenService
```

- [ ] **Step 4: Replace `_generate_debrief` and `_athlete_context` with async `_build_athlete_context`**

Remove the old sync `_athlete_context` function entirely. Replace `_generate_debrief` and add new helpers:

```python
async def _generate_debrief(
    activity: Activity,
    context: AthleteContext,
    values: dict[str, object],
) -> dict[str, str]:
    activity_input = _activity_input(activity, values)
    return await generate_debrief(activity_input, context)


async def _build_athlete_context(
    session: AsyncSession,
    athlete_id: int,
    profile: AthleteProfile | None,
) -> AthleteContext:
    load = await _latest_load(session, athlete_id)
    tss_avg = await _tss_30d_avg(session, athlete_id)
    target = await _find_nearest_target(session, athlete_id)
    return AthleteContext(
        lthr=profile.lthr if profile and profile.lthr else 155,
        threshold_pace_sec_km=_threshold_pace(profile),
        tss_30d_avg=tss_avg,
        acwr=load.acwr if load else 1.0,
        ctl=load.ctl if load else 0.0,
        atl=load.atl if load else 0.0,
        tsb=load.tsb if load else 0.0,
        training_phase=_training_phase_for_target(target),
        race_target=_race_target_context(target) if target else None,
    )


async def _latest_load(session: AsyncSession, athlete_id: int) -> LoadHistory | None:
    result = await session.execute(
        select(LoadHistory)
        .where(LoadHistory.athlete_id == athlete_id)
        .order_by(LoadHistory.date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _tss_30d_avg(session: AsyncSession, athlete_id: int) -> float:
    cutoff = date.today() - timedelta(days=30)
    result = await session.execute(
        select(func.avg(ActivityMetrics.hr_tss))
        .join(Activity, Activity.id == ActivityMetrics.activity_id)
        .where(
            ActivityMetrics.athlete_id == athlete_id,
            ActivityMetrics.hr_tss.isnot(None),
            Activity.start_date >= cutoff,
        )
    )
    avg = result.scalar_one_or_none()
    return float(avg) if avg else 60.0


async def _find_nearest_target(session: AsyncSession, athlete_id: int) -> RaceTarget | None:
    result = await session.execute(
        select(RaceTarget)
        .where(
            RaceTarget.athlete_id == athlete_id,
            RaceTarget.race_date >= date.today(),
            RaceTarget.priority == Priority.A,
        )
        .order_by(RaceTarget.race_date)
        .limit(1)
    )
    return result.scalar_one_or_none()


def _race_target_context(target: RaceTarget) -> RaceTargetContext:
    weeks_out = max((target.race_date - date.today()).days // 7, 0)
    return RaceTargetContext(
        race_name=target.race_name,
        weeks_out=weeks_out,
        distance_km=target.distance_km,
        goal_time_sec=target.goal_time_sec,
        training_phase=_compute_phase_from_weeks(weeks_out),
    )


def _training_phase_for_target(target: RaceTarget | None) -> str:
    if target is None:
        return "Base"
    weeks_out = (target.race_date - date.today()).days // 7
    return _compute_phase_from_weeks(weeks_out)


def _compute_phase_from_weeks(weeks_out: int) -> str:
    if weeks_out <= 3:
        return "Taper"
    if weeks_out <= 7:
        return "Peak"
    if weeks_out <= 15:
        return "Build"
    return "Base"
```

- [ ] **Step 5: Update `process_activity_metrics` to use `_build_athlete_context`**

Replace the existing `process_activity_metrics`:

```python
async def process_activity_metrics(session: AsyncSession, activity: Activity) -> None:
    if not _should_compute_metrics(activity):
        await session.commit()
        return
    profile = await _find_profile(session, activity.athlete_id)
    metrics, values = _compute_metrics(activity, profile)
    context = await _build_athlete_context(session, activity.athlete_id, profile)
    session.add(metrics)
    activity.debrief = await _generate_debrief(activity, context, values)
    activity.processing_status = "done"
    await session.commit()
```

- [ ] **Step 6: Add `_push_description` function**

Add after `process_activity_metrics`:

```python
async def _push_description(
    session: AsyncSession,
    activity: Activity,
    client: StravaClientProtocol,
    access_token: str,
) -> None:
    if not settings.strava_push_description:
        return
    if activity.debrief is None:
        return
    result = await session.execute(
        select(ActivityMetrics).where(ActivityMetrics.activity_id == activity.id)
    )
    metrics = result.scalar_one_or_none()
    if metrics is None:
        return
    load = await _latest_load(session, activity.athlete_id)
    acwr = load.acwr if load else 1.0
    z2_pct = float((metrics.zone_distribution or {}).get("z2_pct", 0.0))
    description = format_strava_description(
        tss=metrics.hr_tss or 0.0,
        acwr=acwr,
        z2_pct=z2_pct,
        hr_drift_pct=metrics.hr_drift_pct or 0.0,
        decoupling_pct=metrics.aerobic_decoupling_pct or 0.0,
        next_action=str(activity.debrief.get("next_session_action", "")),
        deep_dive_url=(
            f"{settings.frontend_url}/activities/{activity.id}"
            f"?athlete_id={activity.athlete_id}"
        ),
    )
    try:
        await client.update_activity_description(
            access_token, activity.strava_activity_id, description
        )
    except Exception:
        logger.warning(
            "failed to push description to Strava for activity %s",
            activity.id,
            exc_info=True,
        )
```

- [ ] **Step 7: Call `_push_description` from `_fetch_store_process`**

Replace `_fetch_store_process`:

```python
async def _fetch_store_process(
    session: AsyncSession,
    athlete_id: int,
    strava_activity_id: int,
    client: StravaClientProtocol,
    access_token: str,
) -> IngestionResult:
    data = await client.get_activity(access_token, strava_activity_id)
    streams = await client.get_activity_streams(access_token, strava_activity_id)
    activity = _build_activity(athlete_id, strava_activity_id, data, streams)
    await _persist_activity(session, activity)
    try:
        await process_activity_metrics(session, activity)
    except Exception:
        activity.processing_status = "failed"
        await session.commit()
        raise
    await _push_description(session, activity, client, access_token)
    return IngestionResult(status="stored", activity_id=activity.id)
```

- [ ] **Step 8: Run the new push tests**

```bash
~/.pyenv/versions/3.13.9/bin/python -m pytest tests/test_services/test_activity_ingestion.py -v
```

Expected: `4 passed`

- [ ] **Step 9: Run full test suite**

```bash
~/.pyenv/versions/3.13.9/bin/python -m pytest tests/ -q
```

Expected: `50 passed`

- [ ] **Step 10: Commit**

```bash
git add backend/app/services/activity_ingestion.py \
        backend/tests/test_services/test_activity_ingestion.py
git commit -m "feat: real athlete context + _push_description in ingestion pipeline"
```

---

## Task 7: Add `activity:write` to OAuth scope

**Files:**
- Modify: `backend/app/services/strava_client.py`

- [ ] **Step 1: Update `get_authorization_url`**

Find this line in `get_authorization_url`:

```python
"scope": "read,activity:read_all,profile:read_all",
```

Replace with:

```python
"scope": "read,activity:read_all,activity:write,profile:read_all",
```

- [ ] **Step 2: Run full test suite — confirm no regression**

```bash
~/.pyenv/versions/3.13.9/bin/python -m pytest tests/ -q
```

Expected: `49 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/strava_client.py
git commit -m "feat: add activity:write to Strava OAuth scope for description push"
```

---

## Post-Implementation Checklist

- [ ] Set `STRAVA_PUSH_DESCRIPTION=true` in `backend/.env` (default is `false`)
- [ ] Existing connected athletes must re-connect Strava via `/auth/strava` to grant `activity:write`
- [ ] Verify on Strava app settings page that `activity:write` is listed under allowed scopes
- [ ] Run a test workout and confirm the 4-line block appears on the Strava activity

---

## SQL for new columns (no Alembic — run manually against Postgres)

The `athletes` table needs `avatar_url`, `city`, `country` from the previous session. Run if not already done:

```sql
ALTER TABLE athletes ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500);
ALTER TABLE athletes ADD COLUMN IF NOT EXISTS city VARCHAR(100);
ALTER TABLE athletes ADD COLUMN IF NOT EXISTS country VARCHAR(100);
```
