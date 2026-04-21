# Training plan import — "Plan vs Actual" coaching context — Design

**Date**: 2026-04-21
**Status**: Draft (awaiting user review)
**Scope**: 1 new table + 1 settings column, 1 new service module, 1 new router, 2 frontend page additions, prompt + debrief output extension

---

## Problem

The AI coach currently reasons only about what the athlete did (Strava) versus physiological thresholds (CTL/ATL/TSB/ACWR). It has no notion of what the athlete was *supposed* to do on any given day. That makes two classes of advice impossible:

1. **Compliance signal** — "Today was supposed to be 60min Z2 recovery. You ran 90min Z3. The plan is broken; tomorrow is now recovery regardless of what your coach wrote."
2. **Continuity** — "You have a 4h long run scheduled Saturday. Today's HR drift of 9% says your base isn't there yet — downgrade Saturday to 3h or move the quality session to next week."

Without a planned-workout reference, every debrief is stateless. The coach doesn't "remember" intent.

## Goals

- Let the athlete (self-coached, single user for MVP) maintain their weekly plan in a single Google Sheet and have the AI read it automatically.
- Expose the planned workout for today (and tomorrow) into the debrief pipeline's `AthleteContext`.
- Teach the LLM to diagnose compliance gaps with specific numbers and adjust `next_session_action` when today broke the plan.
- Show planned-vs-actual on the dashboard and the activity detail page so the signal is visible, not just baked into the debrief text.

## Non-goals (MVP exclusions — YAGNI)

- No Google OAuth. The sheet must be "Published to web as CSV"; we fetch the public URL.
- No column-mapping UI. The template column order and header row are fixed; mismatched files are rejected with a sync report.
- No `.xlsx` file upload. CSV only (Google Sheets → publish → CSV works; Excel users can export CSV).
- No missed-session detection (planned day, no activity logged). Future scheduled job.
- No weekly-aggregate comparison (daily rows only).
- No planned-vs-actual line overlay on the `LoadChart`. Deferred.
- No multi-coach / multi-plan support. One active sheet per athlete.
- No editing planned entries in the app. Source of truth is the sheet.

---

## Architecture

```
Google Sheet (coach / self-authored)
    └─ File > Share > Publish to web > CSV  →  view-only public URL

Athlete settings
    └─ Targets page > "Training Plan" section
        ├─ paste sheet CSV URL → PUT /plan/config
        └─ "Sync now" button   → POST /plan/sync

Backend
    ├─ services/plan_import.py     (pure parser + httpx fetcher, testable)
    ├─ routers/plan.py             (4 endpoints)
    ├─ models/training_plan.py     (new ORM model)
    ├─ athletes.plan_sheet_url     (new settings columns on athletes)
    ├─ workers/activity_processor  (existing) now calls sync + enriches context
    └─ agents/
        ├─ schema.py               (+ PlannedWorkoutContext, + fields on AthleteContext)
        ├─ prompts.py              (+ PLAN VS ACTUAL section, + PLANNED_TOMORROW block)
        └─ debrief_graph.py        (+ plan_compliance tool field, + DebriefOutput field)

Frontend
    ├─ pages/Targets.tsx           (+ Training Plan section)
    ├─ pages/Dashboard.tsx         (+ "This week" planned strip)
    ├─ pages/ActivityDetail.tsx    (+ Planned vs Actual block)
    └─ api/client.ts               (+ hooks: usePlanConfig, useSyncPlan, usePlannedRange)
```

---

## Data model

### New table `training_plan_entries`

Migration `backend/migrations/versions/005_training_plan.py` (down_revision `004_activity_desc_hash`).

| column | type | constraints | notes |
|---|---|---|---|
| `id` | SERIAL | PK | |
| `athlete_id` | INTEGER | FK → athletes.id ON DELETE CASCADE, NOT NULL | indexed |
| `date` | DATE | NOT NULL | |
| `workout_type` | TEXT | NOT NULL, CHECK in enum | see below |
| `planned_tss` | REAL | NULLABLE | |
| `planned_duration_min` | INTEGER | NULLABLE | |
| `planned_distance_km` | REAL | NULLABLE | |
| `planned_elevation_m` | INTEGER | NULLABLE | |
| `description` | TEXT | NULLABLE | free-text from the sheet ("8×400m @ 5k pace, 90s rest") |
| `source` | TEXT | NOT NULL DEFAULT `'sheet_csv'` | `sheet_csv` \| `manual` |
| `imported_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

Indexes / constraints:
- `UNIQUE (athlete_id, date)` — supports later-wins upsert
- `CREATE INDEX ix_training_plan_athlete_date ON training_plan_entries (athlete_id, date)`

**`workout_type` enum** (stored as TEXT + CHECK constraint — keeps migrations simple):

```
recovery, easy, long, tempo, interval, hill, race, rest, cross, strength
```

Rejected values fail the row, not the whole sync.

### New columns on `athletes`

Migration adds to the same `005` revision:

- `plan_sheet_url` TEXT NULLABLE
- `plan_synced_at` TIMESTAMPTZ NULLABLE

---

## CSV template (fixed)

First row is the exact header; columns in this order; extra trailing columns ignored; missing required columns = whole sync fails with a helpful message.

```
date,workout_type,planned_tss,planned_duration_min,planned_distance_km,planned_elevation_m,description
2026-04-22,long,180,240,35,1200,"4h trail Z2, practice fueling every 30min"
2026-04-23,recovery,40,45,7,50,"flat, HR < LTHR-30"
2026-04-24,rest,,,,,
2026-04-25,interval,95,75,12,150,"20min WU / 6×800m @ 5k pace 2min rest / 15min CD"
```

Parsing rules:
- `date` required; ISO `YYYY-MM-DD`. Blank or unparseable → row rejected with reason.
- `workout_type` required; lowercased; must be in enum.
- Numeric cells: blank → NULL; non-numeric → row rejected with reason.
- `description` trimmed; max 1000 chars (anything longer truncated + logged).

---

## Ingest service — `backend/app/services/plan_import.py`

Pure functions where possible; I/O isolated.

```python
# Pure — unit-testable with golden CSV fixtures
def parse_plan_csv(text: str) -> tuple[list[ParsedEntry], list[ParseError]]: ...

# Thin I/O — httpx GET, enforces published-CSV URL pattern
async def fetch_plan_sheet(url: str) -> str: ...

# Orchestrator — fetch → parse → upsert (later-wins)
async def sync_plan(
    athlete_id: int, db: AsyncSession
) -> SyncReport: ...

# Called from activity worker before building AthleteContext
async def get_planned_for_date(
    athlete_id: int, date_: date, db: AsyncSession
) -> PlannedWorkoutContext | None: ...
```

- **URL validation**: regex-enforce `^https://docs\.google\.com/spreadsheets/.*/pub\?.*output=csv`. Anything else → 400 at the `PUT /plan/config` endpoint.
- **Fetch timeout**: 10s. Failure → return `SyncReport(status='failed', error=...)`, do not mutate DB.
- **Upsert**: `INSERT ... ON CONFLICT (athlete_id, date) DO UPDATE` — the sheet is authoritative. (The `source` column is `sheet_csv` for every MVP row; the `manual` value is reserved for a future in-app editor and has no write path yet.)
- **Sync report shape**:

```python
class SyncReport(BaseModel):
    status: Literal["ok", "failed"]
    fetched_rows: int
    accepted: int
    rejected: list[RowError]  # { row_number, reason }
    error: str | None          # only when status=failed
```

Sync triggers:
1. Manual — `POST /plan/sync { athlete_id }` returns the report synchronously
2. Automatic — fire-and-forget at the start of `workers/activity_processor` before the debrief call, guarded by `if athlete.plan_sheet_url`. Sync failures never block activity processing (logged, swallowed).

---

## Context enrichment

Extend `backend/app/agents/schema.py`:

```python
class PlannedWorkoutContext(BaseModel):
    date: date
    workout_type: str
    planned_tss: float | None
    planned_duration_min: int | None
    planned_distance_km: float | None
    planned_elevation_m: int | None
    description: str | None

class AthleteContext(BaseModel):
    # ... existing fields unchanged ...
    planned_today: PlannedWorkoutContext | None = None
    planned_tomorrow: PlannedWorkoutContext | None = None
```

Populated in the existing pipeline right after `AthleteContext` is built:

```python
activity_date = activity.start_date.date()
context.planned_today    = await get_planned_for_date(athlete_id, activity_date, db)
context.planned_tomorrow = await get_planned_for_date(athlete_id, activity_date + timedelta(days=1), db)
```

Both fields are optional so existing tests and athletes without a plan are unaffected.

---

## Prompt changes — `backend/app/agents/prompts.py`

### Addition to `SYSTEM_PROMPT`

Inserted between `CADENCE FLAG` block and `CLIMBING/DESCENDING VMM FLAGS` block:

```
=== PLAN VS ACTUAL (only when [PLANNED_WORKOUT_TODAY] is provided) ===
Compute compliance on 3 axes:
- TSS delta:      actual_tss / planned_tss × 100   (report as %)
- Duration delta: actual_min / planned_min × 100
- Type fidelity:  did execution match planned workout_type?

Fidelity rules (actual vs planned workout_type):
- planned recovery|easy, but zone_distribution Z3+Z4+Z5 > 20%   → TYPE BREAK (ran hard on recovery day)
- planned tempo|interval|hill, but Z3+Z4+Z5 < 15%                → TYPE BREAK (skipped the quality)
- planned long, but duration < 75% of planned_duration_min       → TYPE BREAK (cut short)

Flag rules:
- actual_tss > planned_tss × 1.20 AND planned_type in {recovery, easy}
      → "Overcooked an easy day — tomorrow's quality session is now at risk."
- actual_tss < planned_tss × 0.80 AND duration > 10 min
      → "Plan underdelivered — diagnose why (HR drift, RPE, life stress, weather)."
- TYPE BREAK detected
      → Name the specific mismatch with numbers, then override next_session_action
        regardless of what [PLANNED_TOMORROW] says.

Use [PLANNED_TOMORROW] to shape next_session_action. If today broke the plan hard
(two or more axes failed), tomorrow must be recovery, not the planned session.
```

### Addition to `build_debrief_prompt()`

A conditional block appended after the "TODAY'S SESSION" section when `context.planned_today` is present:

```
=== PLANNED WORKOUT (today) ===
Type: long
Planned TSS: 180   Duration: 240 min   Distance: 35 km   D+: 1200 m
Description: 4h trail Z2, practice fueling every 30min

=== PLANNED TOMORROW ===
Type: recovery  Planned TSS: 40  Duration: 45 min
```

Emitted ONLY when the fields exist. If absent, the debrief behaves exactly as today (no plan section, no compliance field in output).

---

## Debrief output extension

`agents/schema.py` `DebriefOutput` gains one field:

```python
plan_compliance: str = Field(default="", max_length=300)
```

Tool schema in `debrief_graph.py` gains a matching property:

```python
"plan_compliance": {
    "type": "string",
    "description": (
        "Score 0-100 + one sentence naming the biggest compliance gap. "
        "Empty string if no plan for this date."
    ),
}
```

`plan_compliance` is **required=False** in the tool schema (Claude omits the key when there's no plan). The rule-based `fallback_debrief` also populates it deterministically using the same 3-axis logic, so the field is never blank when a plan exists — even if the LLM call fails.

**String format contract** (required for the frontend badge parser): when populated, `plan_compliance` MUST start with a 1-3 digit integer 0-100 followed by `/100` and a space, then one sentence. Example: `"62/100 Overcooked an easy day — tomorrow's quality session is now at risk."` This format is enforced in the system prompt and produced verbatim by the fallback.

**Fallback scoring formula** (for `fallback_debrief` and documented in tests):

```
score = 100
# TSS axis
if planned_tss and actual_tss:
    delta = abs(actual_tss - planned_tss) / planned_tss
    score -= min(delta, 1.0) * 40     # up to -40

# Duration axis
if planned_duration_min and actual_duration_min:
    delta = abs(actual_duration_min - planned_duration_min) / planned_duration_min
    score -= min(delta, 1.0) * 30     # up to -30

# Type fidelity axis
if type_break_detected:
    score -= 30                        # flat penalty

score = max(0, round(score))
```

Headline sentence picked by priority: TYPE BREAK > overcooked > underdelivered > "On target."

---

## API surface — `backend/app/routers/plan.py`

| Method | Path | Query / body | Response | Notes |
|---|---|---|---|---|
| `PUT` | `/plan/config` | `{ athlete_id, sheet_url }` | `{ athlete_id, sheet_url, plan_synced_at }` | Validates URL pattern. Does NOT trigger sync automatically — the UI calls `/plan/sync` next. |
| `POST` | `/plan/sync` | `{ athlete_id }` | `SyncReport` | Synchronous; returns report for UI. |
| `GET` | `/plan` | `?athlete_id=&from=&to=` | `list[PlanEntryOut]` | Used by Dashboard strip and ActivityDetail. Inclusive date range. |
| `DELETE` | `/plan/config` | `?athlete_id=` | `204` | Clears `plan_sheet_url` and `plan_synced_at`. Keeps historical entries. |

`PlanEntryOut` mirrors the DB columns minus `imported_at` and `source`.

---

## Frontend

### Targets page — new "Training Plan" section

Below the existing race targets list:

```
┌─ Training Plan ────────────────────────────────────────────┐
│ Google Sheets published CSV URL:                            │
│ [https://docs.google.com/spreadsheets/d/.../pub?output=csv] │
│                                                             │
│ [ Save ]  [ Sync now ]                                      │
│                                                             │
│ Last synced: 2026-04-21 14:03 (7 entries, 0 rejected)       │
│                                                             │
│ ▸ Rejected rows (if any):                                   │
│    • row 14: workout_type "fartlek" not recognised          │
│    • row 17: date "next monday" not ISO                     │
│                                                             │
│ [ Need a template? Copy it → ] (opens static Google Sheet)  │
└─────────────────────────────────────────────────────────────┘
```

Template sheet URL is a hardcoded constant in `frontend/src/api/client.ts` (a single Google Sheet we publish once, anyone can `File > Make a copy`).

### Dashboard — "This week" strip

New row above the existing load chart, only rendered when `GET /plan?from=today&to=today+6d` returns ≥ 1 entry:

```
┌─ This week (planned) ──────────────────────────────────────┐
│ Today   Tue    Wed    Thu    Fri    Sat        Sun         │
│ long    easy   rest   tempo  easy   long       recovery    │
│ 180     40     —      95     50     220        30          │
│ TSS                                                        │
└────────────────────────────────────────────────────────────┘
```

Today highlighted. Click a day → future enhancement (link to planned detail). Out of scope for MVP.

### ActivityDetail — "Planned vs Actual" block

Only rendered when the activity's date has a plan entry. Sits above the existing DebriefCard:

```
┌─ Planned vs Actual ──────────────────────── Compliance: 62 │
│ "Overcooked an easy day — tomorrow's quality session is    │
│  now at risk." — from debrief.plan_compliance              │
│                                                            │
│          Planned        Actual           Δ                 │
│ Type     easy           long             TYPE BREAK        │
│ TSS       60            142              +137%             │
│ Duration 60 min         112 min          +87%              │
│ Notes    "flat Z2, HR < LTHR-15"                           │
└────────────────────────────────────────────────────────────┘
```

Compliance badge colour:
- 90-100 → green
- 70-89  → yellow
- 0-69   → red

Pure rendering component. No computation in the browser — badge colour derives from the numeric prefix in `debrief.plan_compliance`. If the field starts with a non-digit, badge is hidden but the sentence is still shown.

---

## Testing strategy

### Backend

- `test_plan_import_parser`
  - golden valid CSV → N entries, 0 errors
  - blank cells allowed → NULLs preserved
  - bad workout_type → row rejected with reason
  - bad date → row rejected
  - missing header columns → whole file rejected
  - trailing extra columns → ignored, not errored
  - duplicate dates in one file → later row wins (document + test)
- `test_plan_import_fetch`
  - non-Google URL → ValidationError
  - httpx timeout → SyncReport status=failed
  - valid CSV body → returned as string
- `test_plan_sync_upsert`
  - second sync changes existing date → row updated, not duplicated
- `test_context_enrichment`
  - activity has matching plan date → `planned_today` populated
  - no plan → `planned_today` is None
- `test_prompt_emission`
  - no plan → no PLANNED_WORKOUT section in prompt
  - plan present → section rendered with exact expected format
- `test_fallback_compliance_score`
  - deterministic 3-axis scoring matches manually computed values for a handful of fixtures

### Frontend

- Targets page: paste invalid URL → inline error (no server call)
- Targets page: Sync now failure → red banner with reason
- Dashboard: empty `GET /plan` → strip not rendered
- ActivityDetail: `plan_compliance` starts with `87` → yellow badge; starts with letter → badge hidden

### Manual smoke

- Publish a real Google Sheet, paste URL, sync, let a new Strava activity come in via webhook, open ActivityDetail, confirm the Planned vs Actual block renders and the debrief text references the planned type.

---

## Rollout

Single migration `005_training_plan`. No backfill. Existing athletes without `plan_sheet_url` are completely unaffected (every new codepath is guarded by nullability). Ship behind no flag — it's additive.

## Commit sequence (for the implementation plan to expand)

1. `chore: alembic 005 — training_plan_entries + athletes.plan_sheet_url`
2. `feat: plan_import service (parser + fetcher + upsert) with unit tests`
3. `feat: /plan router (PUT config, POST sync, GET range, DELETE config)`
4. `feat: enrich AthleteContext with planned_today / planned_tomorrow`
5. `feat: prompt additions + plan_compliance tool field + fallback scoring`
6. `feat: Targets page — Training Plan section`
7. `feat: Dashboard — This week strip`
8. `feat: ActivityDetail — Planned vs Actual block`
9. `test: integration — webhook → sync → context → debrief emits plan_compliance`

---

## Open questions (flag before implementation)

1. Should `workers/activity_processor` await the sync or fire-and-forget? Design says fire-and-forget to protect activity latency — confirm you accept that the *very first* activity after a sheet edit may use the previous snapshot.
2. Should unrecognised `workout_type` values be auto-coerced (e.g. "fartlek" → "interval") or strictly rejected? Design says strictly rejected; easy to change.
3. Template sheet hosting — do you want the template URL baked into the frontend, or served from a backend config endpoint so we can change it without a frontend deploy?
