# Webhook-only activity ingest — Design

**Date**: 2026-04-21
**Status**: Draft (awaiting user review)
**Scope**: 1 column migration, 1 reactive code path removed, 1 OAuth-callback hook added, worker bookkeeping, tests.

---

## Problem

Strava imposes a daily read-rate limit, and recent outages (see commits `7105e03`, `4dc3cc7`, `2ceef98`) have all traced back to read-budget exhaustion. Investigation of the codebase found **no periodic poller** (no APScheduler, cron, or `while True` loop), but one reactive code path behaves like polling under normal usage:

`GET /dashboard/load` auto-triggers `enqueue_backfill` as a `BackgroundTask` whenever the athlete has `< 10` activities in the DB (`backend/app/routers/dashboard.py:63-65`). There is no dedup, no throttle, and no lock. Each call to `backfill_recent_activities` costs **~21 Strava reads** (1 list-summaries + 10 × (activity + streams)). A user who opens the dashboard 5 times in a minute fires 5 parallel backfills ≈ 100 reads. Multiplied across a day this is the load-bearing cause of the daily-limit exhaustion.

Webhooks already handle every new activity cleanly (`backend/app/routers/webhook.py`). What's missing is a clean "first-time history backfill" trigger that runs exactly once per athlete, outside the dashboard request path.

## Goals

- Remove the reactive backfill from `/dashboard/load` entirely. That endpoint should never hit Strava.
- Trigger backfill exactly once per athlete, at OAuth connect, gated by a persisted flag.
- Preserve the manual ops script (`scripts/reregister_and_backfill.py`) as-is for outage recovery.
- Keep all ongoing new-activity ingestion on webhooks (already the case).

## Non-goals (YAGNI)

- No "syncing recent activities…" UI indicator on the dashboard. File as a future UX polish; MVP users tolerate an empty dashboard for the ~15-30s backfill.
- No admin endpoint to reset `backfilled_at`. The ops script covers the rare outage-recovery case.
- No dedup/lock on concurrent backfill runs. Only happens on rapid OAuth reconnect (rare); webhook upsert is already idempotent by `(athlete_id, strava_activity_id)`, so concurrent fetches of the same activity are safe.
- No change to `backfill_recent_activities`'s 21-read-per-call shape. Strava's list-summaries endpoint doesn't include stream data, so we still need 2 fetches per new activity (activity + streams).
- No change to webhook handling, token refresh, or retry logic. Those are working.
- No removal of `get_athlete_activities` from the Strava client — still used by OAuth backfill and the ops script.

---

## Architecture

```
Strava
   ├─ webhook events → POST /webhook/strava  → enqueue_activity
   │                                          → ingest_activity
   │                                          → fetch(activity + streams)
   │                                          → metrics + debrief + push description
   │
   └─ list-summaries + activities (only on OAuth connect, once per athlete)
             ↑
             └─ auth.strava_callback (NEW trigger)
                   └─ if athlete.backfilled_at is None: enqueue_backfill
                                                        └─ backfill_recent_activities
                                                             └─ sets athlete.backfilled_at on success

Dashboard
   └─ GET /dashboard/load   →  pure DB read. No Strava calls. Ever.
```

---

## Data model

### Migration `006_athlete_backfilled_at.py`

```sql
ALTER TABLE athletes ADD COLUMN IF NOT EXISTS backfilled_at TIMESTAMPTZ;
```

`down_revision = "005_training_plan"`. Downgrade drops the column.

### ORM

`backend/app/models/athlete.py` — add one column before `created_at` (alongside the `plan_sheet_url` / `plan_synced_at` columns added in the prior feature):

```python
backfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

No new relationship.

---

## Code changes

### A. Remove the reactive backfill from `/dashboard/load`

File: `backend/app/routers/dashboard.py`

Before (lines 55-72):

```python
@router.get("/load", response_model=DashboardLoadOut)
async def get_load(
    athlete_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> DashboardLoadOut:
    history = await load_history(db, athlete_id)
    target = await nearest_a_target(db, athlete_id)
    count = await activity_count(db, athlete_id)
    if count < 10:
        background_tasks.add_task(enqueue_backfill, athlete_id)
    return DashboardLoadOut(...)
```

After:

```python
@router.get("/load", response_model=DashboardLoadOut)
async def get_load(
    athlete_id: int,
    db: AsyncSession = Depends(get_db),
) -> DashboardLoadOut:
    history = await load_history(db, athlete_id)
    target = await nearest_a_target(db, athlete_id)
    return DashboardLoadOut(...)
```

Also:
- Remove `from fastapi import ..., BackgroundTasks` (the only caller)
- Remove `from app.workers.tasks import enqueue_backfill`
- Remove the now-unused `activity_count` helper function

### B. OAuth callback triggers one-time backfill

File: `backend/app/routers/auth.py`

Add `BackgroundTasks` to the callback signature, and after the successful `await db.commit()` (line 51):

```python
@router.get("/callback")
async def strava_callback(
    background_tasks: BackgroundTasks,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    # ... existing state + exchange + upsert + commit ...

    if athlete.backfilled_at is None:
        background_tasks.add_task(enqueue_backfill, athlete.id)

    return RedirectResponse(f"{settings.frontend_url}/setup?athlete_id={athlete.id}")
```

Add `from fastapi import BackgroundTasks` and `from app.workers.tasks import enqueue_backfill` to the imports.

The check is on `athlete.backfilled_at is None`, so:
- First-ever connect → fires backfill.
- Reconnect after completed backfill → does NOT fire.
- Reconnect after a failed backfill (backfilled_at still null) → retries. Acceptable — user-initiated action, rare.

### C. Worker marks success

File: `backend/app/services/activity_ingestion.py::backfill_recent_activities`

Current shape (lines 63-87):

```python
async def backfill_recent_activities(
    session, athlete_id, client, token_service, limit=10,
) -> int:
    credential = await _find_credential(session, athlete_id)
    if credential is None:
        return 0
    token = await _get_valid_token(session, credential, client, token_service)
    summaries = await client.get_athlete_activities(token, per_page=limit)
    # ... loop over summaries ...
    return count
```

New shape — set `backfilled_at` after the loop completes without the list-summaries call blowing up:

```python
async def backfill_recent_activities(
    session, athlete_id, client, token_service, limit=10,
) -> int:
    credential = await _find_credential(session, athlete_id)
    if credential is None:
        return 0
    token = await _get_valid_token(session, credential, client, token_service)
    summaries = await client.get_athlete_activities(token, per_page=limit)
    strava_ids = [s["id"] for s in summaries if "id" in s]
    existing = await _get_existing_strava_ids(session, athlete_id, strava_ids)
    count = 0
    for summary in summaries:
        strava_id = summary.get("id")
        if strava_id is None or strava_id in existing:
            continue
        try:
            await _fetch_store_process(session, athlete_id, strava_id, client, token)
            count += 1
        except Exception:
            logger.warning("backfill skipped activity %s", strava_id, exc_info=True)

    # Mark the athlete as backfilled. We reached the end of the list-summaries
    # loop; individual per-activity failures inside the loop are tolerable
    # (already logged). A truly broken backfill would have raised from the
    # list-summaries call above and we'd never get here.
    athlete = await session.get(Athlete, athlete_id)
    if athlete is not None:
        athlete.backfilled_at = datetime.now(timezone.utc)
        await session.commit()

    return count
```

Import tweaks: `Athlete` already imported from `app.models.athlete` in this file. `datetime` and `timezone` already imported from `datetime`.

### D. Ops script unchanged

`backend/scripts/reregister_and_backfill.py` keeps working. The operator expects "running this always backfills." Setting `backfilled_at` afterward is fine — it doesn't gate anything outside the OAuth path.

---

## Behavior matrix

| Scenario | Before | After |
|---|---|---|
| New activity from Strava (webhook) | 2 reads (activity + streams) | 2 reads — unchanged |
| User opens dashboard, has ≥10 activities | 0 reads | 0 reads |
| User opens dashboard, has <10 activities | ~21 reads per load | **0 reads** |
| User refreshes dashboard 5× in a minute | ~100 reads (5 × 21) | **0 reads** |
| New user completes OAuth connect | 0 reads at connect; 21 on first dashboard load | ~21 reads at connect; 0 on dashboard |
| Existing user reconnects OAuth (reauth) | 0 reads at connect; 21 on next dashboard load with <10 | 0 reads at connect (backfilled_at already set); 0 reads on dashboard |
| Webhook outage + reconnect | Missed activities still missing | Missed activities still missing — operator runs ops script (unchanged) |

**Net effect**: removes the dominant source of daily-read-limit pressure (dashboard refresh × low-activity users) and moves the one-time cost to OAuth connect where it belongs.

---

## Testing strategy

### Backend

- **`test_dashboard.py`** — augment existing load-endpoint test:
  - Assert that no `enqueue_backfill` / `get_athlete_activities` is invoked during `GET /dashboard/load`. Use `monkeypatch` to raise if either is called.
  - Remove any existing assertions on backfill behavior from the dashboard flow.
- **`test_auth.py`** — two new tests:
  - OAuth callback with a brand-new athlete (no DB row) → creates athlete, commits, and schedules `enqueue_backfill` exactly once in `background_tasks`.
  - OAuth callback with an existing athlete whose `backfilled_at` is set → does NOT schedule backfill.
- **`test_activity_ingestion.py`** (backfill) — two new tests:
  - Successful backfill sets `athlete.backfilled_at` to a tz-aware UTC datetime close to `now`.
  - Backfill where `get_athlete_activities` raises does NOT set `backfilled_at` (tolerable: we'll retry next connect).
- **`test_activity_ingestion.py`** — one existing test may need updating: `backfill_recent_activities` currently doesn't assert on `backfilled_at`, that's fine.

### Frontend

No frontend changes in this feature. Pure backend/DB.

### Manual smoke

1. Apply migration 006, verify `backfilled_at IS NULL` for all existing athletes.
2. Load `/dashboard/load` as an athlete with 0 activities — verify no Strava call fires (watch network tab / backend logs).
3. Disconnect Strava from app, reconnect OAuth — verify a backfill fires exactly once in the background and `backfilled_at` gets populated.
4. Reconnect again immediately — verify no second backfill fires.

---

## Rollout

- Single migration adds a nullable column. Safe on populated table.
- Existing athletes have `backfilled_at = NULL`. First dashboard load **post-deploy** no longer triggers backfill. If the existing user's activity table is sparse, they'll see an empty dashboard until either (a) they reconnect OAuth (triggers backfill), or (b) the operator runs `scripts/reregister_and_backfill.py`. For the single-user MVP (Duncan), reconnecting once is the cleanest path.
- No feature flag. Additive schema change + behavior removal.

## Commit sequence (for the implementation plan to expand)

1. `chore: alembic 006 — athletes.backfilled_at column + ORM field`
2. `fix: stop auto-triggering backfill from /dashboard/load`
3. `feat: mark athletes.backfilled_at after successful backfill`
4. `feat: trigger one-time backfill on OAuth callback for fresh athletes`
5. `test: dashboard never calls Strava; OAuth backfill is once-per-athlete`

---

## Open questions

1. **Should a "Backfill now" button exist in the UI?** Currently the only way to re-trigger backfill is the ops script or an OAuth reconnect. Design says YAGNI for MVP. Confirm.
2. **Should the manual ops script clear `backfilled_at` before running, so the OAuth callback would re-run on next connect?** Design says no (the script is a complete replacement for backfill on its own). Confirm.
3. **Should `backfilled_at` be advisory (for dedup) or authoritative (used by `/dashboard` to show a loading banner)?** Design says advisory-only for MVP. A "syncing…" banner on the dashboard would be a nice follow-up but is out of scope here.
