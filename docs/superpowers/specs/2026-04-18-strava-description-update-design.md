# Strava Activity Description Auto-Update

**Date:** 2026-04-18
**Status:** Approved

## Problem

After a workout is processed, the coaching insights (TSS, ACWR, HR drift, next-session advice) live only inside the coaching app. The athlete has to open a separate URL to see them. The goal is to surface the most important signal directly inside Strava — where the athlete already lands after every run.

## Solution

After the ingestion pipeline commits metrics and debrief to the DB, push a compact 4-line coaching block to the Strava activity description via `PATCH /activities/{id}`. The block ends with a deep-dive link back to the coaching app's `ActivityDetail` page.

---

## Description Format

Assembled entirely in Python from computed metrics. No LLM is called to produce the numbers.

```
⚡ TSS {tss:.0f} · ACWR {acwr:.2f} ({zone}) · Z2 {z2:.0f}%
📉 HR drift {hr_drift:.1f}% · decoupling {decoupling:.1f}%
→ {next_session_action}
🔍 {frontend_url}/activities/{activity_id}?athlete_id={athlete_id}
```

**Line breakdown:**

| Line | Source |
|---|---|
| Line 1 | `ActivityMetrics.hr_tss`, latest `LoadHistory.acwr`, `zone_distribution["z2_pct"]` |
| Line 2 | `ActivityMetrics.hr_drift_pct`, `ActivityMetrics.aerobic_decoupling_pct` |
| Line 3 | `DebriefOutput.next_session_action` — the only LLM output in the compact block |
| Line 4 | `settings.frontend_url` + activity DB id + athlete id |

**`next_session_action` rules (enforced in LLM system prompt):**
- Max 120 characters
- Lead with race name + weeks out if target is set: `"VMM 8w: 90' Trail, downhill tech >15% slope"`
- Zero filler words ("great job", "it seems like", "listen to your body")
- One concrete instruction + one metric or terrain cue

**VMM / ultra-trail prompt directive (injected when `race_target` is set):**

When `race_target.race_name` contains "VMM" or `race_target.distance_km >= 80`, add this directive to the system prompt:

> "Prioritise climbing (D+) and technical descent (D-) cues. VMM and ultra-trail races destroy quads on downhill — always include a descent-specific element when TSB > -10 and training_phase is Build or Peak. Prefer gradient targets (>15% slope) over vague terrain labels."

This shifts the LLM output from:
```
→ Trail 90 min Z2, keep effort easy          ← generic
```
to:
```
→ VMM 8w: 90' Trail, downhill tech >15%, quad-load descents    ← race-specific
```

**Gradient for other A-races:** if `race_target` is set but is not VMM/ultra, the directive is omitted and the LLM uses standard trail coaching cues.

---

## Architecture

### Data Flow

```
Webhook POST → enqueue_activity (BackgroundTasks)
  → ingest_activity
      → _find_athlete, _find_credential, _get_valid_token
      → _fetch_store_process
          → client.get_activity()
          → client.get_activity_streams()
          → _build_activity()
          → _persist_activity()          ← flush
          → process_activity_metrics()   ← compute metrics + LLM debrief + commit
          → [NEW] _push_description()    ← PATCH Strava, swallows all errors
```

### New Units

| Unit | Location | Responsibility |
|---|---|---|
| `format_strava_description()` | `services/description_builder.py` | Pure function. Takes metric values → returns 4-line string. No DB, no HTTP. Fully unit-testable. |
| `acwr_zone_label()` | `services/description_builder.py` | Maps ACWR float → "green" / "caution" / "injury risk" / "underload". Replaces duplicate in `debrief_graph.py`. |
| `StravaClient.update_activity_description()` | `services/strava_client.py` | `PATCH /activities/{id}` with `{"description": text}`. Added to `StravaClientProtocol`. |
| `_push_description()` | `services/activity_ingestion.py` | Queries metrics + latest ACWR, calls builder, calls client. All failures logged and swallowed. |
| `STRAVA_PUSH_DESCRIPTION` | `config.py` | `bool = False`. Must be set `true` explicitly. Prevents staging/test runs from writing to real Strava data. |

---

## Schema Changes

### `AthleteContext` (extended)

```python
class RaceTargetContext(BaseModel):
    race_name: str
    weeks_out: int
    distance_km: float
    goal_time_sec: int | None   # optional — included when set
    training_phase: str         # Base / Build / Peak / Taper

class AthleteContext(BaseModel):
    lthr: int
    threshold_pace_sec_km: int
    tss_30d_avg: float
    acwr: float
    ctl: float
    atl: float
    tsb: float
    training_phase: str
    race_target: RaceTargetContext | None  # None when no A-race is configured
```

### `_athlete_context()` fix

Currently hardcodes `acwr=1.0`, `tss_30d_avg=60.0`, `ctl/atl/tsb=50/50/0`. These must be replaced with real values:

- `acwr`, `ctl`, `atl`, `tsb` → latest row from `LoadHistory` for this athlete
- `tss_30d_avg` → average of `ActivityMetrics.hr_tss` over the last 30 days
- `race_target` → nearest A-priority `RaceTarget` with `race_date >= today`

---

## OAuth Scope Change

`get_authorization_url()` scope changes from:
```
read,activity:read_all,profile:read_all
```
to:
```
read,activity:read_all,activity:write,profile:read_all
```

**Impact:** Existing connected athletes must re-authenticate once to grant `activity:write`. Without it, `PATCH` returns 403 and the push is skipped with a warning log — ingestion still succeeds.

---

## Error Handling

| Failure | Behaviour |
|---|---|
| 403 — missing `activity:write` scope | `logger.warning("activity:write scope not granted")`, skip |
| 429 — Strava rate limit | `logger.warning(...)`, skip — no retry |
| Any other HTTP error | `logger.warning(...)`, swallow |
| No A-priority target | `race_target=None`, LLM gives generic but crisp advice |
| No `LoadHistory` rows yet (new athlete) | `acwr=1.0` default, `ctl/atl/tsb=0` |
| `STRAVA_PUSH_DESCRIPTION=false` | Early return, no PATCH call made |

The description push **never raises** — `process_activity_metrics` has already committed, so the activity is in a good state regardless.

---

## Feature Flag

```env
# backend/.env
STRAVA_PUSH_DESCRIPTION=false   # set true to enable
```

Default `false`. Switch to `true` once `activity:write` scope is confirmed on the Strava app settings page.

---

## Testing

| Test | What it covers |
|---|---|
| `test_format_strava_description` | Pure function with/without race target, with/without goal time |
| `test_acwr_zone_label` | All four zones |
| `test_push_description_skipped_when_flag_off` | `STRAVA_PUSH_DESCRIPTION=false` → client never called |
| `test_push_description_swallows_http_error` | Client raises `httpx.HTTPStatusError` → ingestion result still `"stored"` |
| `test_athlete_context_uses_real_load_values` | `_athlete_context()` returns values from `LoadHistory`, not hardcoded |

---

## Files Changed

```
backend/app/
  agents/schema.py                   ← add RaceTargetContext, extend AthleteContext
  services/description_builder.py    ← NEW: format_strava_description(), acwr_zone_label()
  services/strava_client.py          ← add update_activity_description() to client + protocol
  services/activity_ingestion.py     ← fix _athlete_context(), add _push_description()
  config.py                          ← add STRAVA_PUSH_DESCRIPTION bool
backend/tests/
  test_services/test_description_builder.py   ← NEW
  test_services/test_activity_ingestion.py    ← extend with push tests
```
