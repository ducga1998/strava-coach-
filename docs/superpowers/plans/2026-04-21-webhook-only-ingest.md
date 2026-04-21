# Webhook-Only Activity Ingest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the reactive `enqueue_backfill` trigger from `/dashboard/load` (the dominant source of Strava daily-read-limit exhaustion) and move the one-time history backfill to the OAuth callback, gated by a new `athletes.backfilled_at` column so it fires exactly once per athlete.

**Architecture:** Additive column (`backfilled_at TIMESTAMPTZ NULL`). One callsite removed from dashboard router. One callsite added to OAuth callback with a null-guard. Worker sets the column on successful backfill completion. Webhook ingestion path (already the primary source of new activities) is unchanged.

**Tech Stack:** FastAPI + SQLAlchemy 2 async + Alembic + pytest + BackgroundTasks. No frontend changes.

**Spec:** `docs/superpowers/specs/2026-04-21-webhook-only-ingest-design.md`

**Working directory:** Run backend tests from `backend/`.

**Base branch HEAD at plan time:** commit `1905aaf` on `feat/webhook-only-ingest`.

---

## Task 1: Alembic migration 006 + ORM column

**Files:**
- Create: `backend/migrations/versions/006_athlete_backfilled_at.py`
- Modify: `backend/app/models/athlete.py`

- [ ] **Step 1: Create the migration file**

`backend/migrations/versions/006_athlete_backfilled_at.py`:

```python
"""Add athletes.backfilled_at to gate one-time history backfill.

Set once by the backfill worker after successful completion; checked by
the OAuth callback to decide whether to enqueue a backfill. Null means
"never backfilled"; any non-null datetime means "skip".

Revision ID: 006_athlete_backfilled_at
Revises: 005_training_plan
Create Date: 2026-04-21

"""
from typing import Sequence, Union

from alembic import op


revision: str = "006_athlete_backfilled_at"
down_revision: Union[str, None] = "005_training_plan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS backfilled_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE athletes DROP COLUMN IF EXISTS backfilled_at")
```

- [ ] **Step 2: Extend the ORM model**

In `backend/app/models/athlete.py`, add one column inside the `Athlete` class. Place it alongside the `plan_sheet_url` / `plan_synced_at` columns added in the prior feature (directly before `created_at`):

```python
    plan_sheet_url: Mapped[str | None] = mapped_column(Text)
    plan_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    backfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

No new imports needed — `Mapped`, `mapped_column`, `DateTime`, and `datetime` are already imported.

- [ ] **Step 3: Apply migration**

Run: `cd backend && alembic upgrade head`
Expected output ends with: `Running upgrade 005_training_plan -> 006_athlete_backfilled_at`.

If the dev DB is not running: `docker compose up -d postgres`, then re-run.

- [ ] **Step 4: Verify schema**

Run:
```bash
docker compose exec -T postgres psql -U postgres -d stravacoach -c "\d athletes" | grep backfilled_at
```
Expected: `backfilled_at | timestamp with time zone | | |` (nullable, no default).

- [ ] **Step 5: Run existing tests — no regression**

Run: `cd backend && python -m pytest tests/ -x -q`
Expected: same test count as before this branch (around 219 if training-plan-import is already merged/rebased; otherwise ~167 on fresh main). All green.

- [ ] **Step 6: Commit**

```bash
git add backend/migrations/versions/006_athlete_backfilled_at.py backend/app/models/athlete.py
git commit -m "chore: alembic 006 — athletes.backfilled_at column + ORM field"
```

---

## Task 2: Worker sets `backfilled_at` on successful backfill

**Files:**
- Modify: `backend/app/services/activity_ingestion.py`
- Create: `backend/tests/test_services/test_backfill_marks_complete.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_services/test_backfill_marks_complete.py`:

```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.credentials import StravaCredential
from app.services.activity_ingestion import backfill_recent_activities


@pytest_asyncio.fixture
async def athlete_with_credential(db_session: AsyncSession) -> Athlete:
    athlete = Athlete(strava_athlete_id=42)
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)

    # The real encryption may want bytes; since we mock token_service.decrypt,
    # the exact on-disk byte shape never matters. If the StravaCredential
    # model rejects bytes here, fall back to str values — the mock short-
    # circuits before decryption is attempted.
    credential = StravaCredential(
        athlete_id=athlete.id,
        access_token_enc=b"fake-access-enc",
        refresh_token_enc=b"fake-refresh-enc",
        expires_at=int(datetime.now(timezone.utc).timestamp()) + 3600,
    )
    db_session.add(credential)
    await db_session.commit()
    return athlete


@pytest.mark.asyncio
async def test_backfill_marks_backfilled_at_on_success(
    db_session: AsyncSession, athlete_with_credential: Athlete
):
    """After a successful backfill (even with zero activities ingested),
    athlete.backfilled_at must be set to a UTC-aware datetime."""
    client = AsyncMock()
    client.get_athlete_activities.return_value = []

    # token_service.decrypt is synchronous in the real service; MagicMock
    # gives us a sync return, matching production behavior.
    token_service = MagicMock()
    token_service.decrypt = MagicMock(return_value="fake-token")

    before = datetime.now(timezone.utc)

    count = await backfill_recent_activities(
        session=db_session,
        athlete_id=athlete_with_credential.id,
        client=client,
        token_service=token_service,
        limit=10,
    )
    assert count == 0  # empty summaries

    await db_session.refresh(athlete_with_credential)
    assert athlete_with_credential.backfilled_at is not None
    # SQLite in tests may strip tzinfo; re-attach UTC if missing, matching
    # the pattern used in test_plan_import_sync.py.
    stamped = athlete_with_credential.backfilled_at
    if stamped.tzinfo is None:
        stamped = stamped.replace(tzinfo=timezone.utc)
    assert stamped >= before


@pytest.mark.asyncio
async def test_backfill_does_not_mark_when_list_summaries_raises(
    db_session: AsyncSession, athlete_with_credential: Athlete
):
    """If the list-summaries call fails, backfilled_at must stay None so
    the next OAuth reconnect will retry."""
    client = AsyncMock()
    client.get_athlete_activities.side_effect = RuntimeError("429 rate limited")

    token_service = MagicMock()
    token_service.decrypt = MagicMock(return_value="fake-token")

    with pytest.raises(RuntimeError, match="429"):
        await backfill_recent_activities(
            session=db_session,
            athlete_id=athlete_with_credential.id,
            client=client,
            token_service=token_service,
            limit=10,
        )

    await db_session.refresh(athlete_with_credential)
    assert athlete_with_credential.backfilled_at is None


@pytest.mark.asyncio
async def test_backfill_no_credential_does_not_mark(
    db_session: AsyncSession
):
    """An athlete with no credential returns early with count=0; backfilled_at
    must stay None (we didn't actually fetch anything)."""
    athlete = Athlete(strava_athlete_id=99)
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)

    client = AsyncMock()
    token_service = MagicMock()
    token_service.decrypt = MagicMock(return_value="fake-token")

    count = await backfill_recent_activities(
        session=db_session,
        athlete_id=athlete.id,
        client=client,
        token_service=token_service,
    )
    assert count == 0

    await db_session.refresh(athlete)
    assert athlete.backfilled_at is None
```

- [ ] **Step 2: Run tests — expect failure**

Run: `cd backend && python -m pytest tests/test_services/test_backfill_marks_complete.py -v`
Expected: all 3 tests fail because `backfill_recent_activities` does not currently touch `backfilled_at`.

- [ ] **Step 3: Update `backfill_recent_activities`**

In `backend/app/services/activity_ingestion.py`, find the function (starts around line 63) and update its body. Replace the current function with:

```python
async def backfill_recent_activities(
    session: AsyncSession,
    athlete_id: int,
    client: StravaClientProtocol,
    token_service: TokenService,
    limit: int = 10,
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

    # We reached the end of the list-summaries loop. Mark the athlete as
    # backfilled so the OAuth callback's null-guard skips subsequent calls.
    # Per-activity failures inside the inner try/except are tolerable and
    # already logged; a fully broken backfill would have raised from
    # get_athlete_activities or _get_valid_token above and we'd never get
    # here.
    athlete = await session.get(Athlete, athlete_id)
    if athlete is not None:
        athlete.backfilled_at = datetime.now(timezone.utc)
        await session.commit()

    return count
```

`Athlete`, `datetime`, and `timezone` are already imported at the top of the file. Verify before committing; if any of them are missing, add them to the existing import blocks (don't add a new `from datetime import ...` line — consolidate with the one that already imports `date, datetime, timedelta`).

- [ ] **Step 4: Run tests — expect pass**

Run: `cd backend && python -m pytest tests/test_services/test_backfill_marks_complete.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the full suite**

Run: `cd backend && python -m pytest tests/ -x -q`
Expected: all green. Prior activity-ingestion tests still pass because they monkeypatch or don't exercise the new commit path.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/activity_ingestion.py backend/tests/test_services/test_backfill_marks_complete.py
git commit -m "feat: mark athletes.backfilled_at after successful backfill"
```

---

## Task 3: Remove the reactive backfill from `/dashboard/load`

**Files:**
- Modify: `backend/app/routers/dashboard.py`
- Create: `backend/tests/test_routers/test_dashboard.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_routers/test_dashboard.py`:

```python
import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.routers import dashboard


def _create_athlete(db_session: AsyncSession, strava_id: int = 1) -> Athlete:
    athlete = Athlete(strava_athlete_id=strava_id)
    db_session.add(athlete)
    asyncio.run(db_session.commit())
    asyncio.run(db_session.refresh(athlete))
    return athlete


def test_dashboard_load_never_calls_enqueue_backfill(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/dashboard/load must never trigger a Strava-hitting backfill.

    Previously a user with <10 activities in DB would fire enqueue_backfill
    on every dashboard load, burning ~21 Strava reads each time. That
    trigger is now removed; this test locks the behavior.
    """
    athlete = _create_athlete(db_session)

    called = False

    async def fake_enqueue_backfill(_athlete_id: int) -> None:
        nonlocal called
        called = True

    # Guard against two possible re-introductions: via the router module
    # or via the workers.tasks module.
    monkeypatch.setattr(
        "app.routers.dashboard.enqueue_backfill",
        fake_enqueue_backfill,
        raising=False,
    )
    monkeypatch.setattr(
        "app.workers.tasks.enqueue_backfill", fake_enqueue_backfill
    )

    response = client.get(f"/dashboard/load?athlete_id={athlete.id}")

    assert response.status_code == 200, response.text
    assert called is False, "dashboard/load must not call enqueue_backfill"


def test_dashboard_load_returns_empty_history_for_new_athlete(
    client: TestClient, db_session: AsyncSession
) -> None:
    """With no LoadHistory and no RaceTarget, the endpoint still responds 200
    with default values — confirming the endpoint is pure DB reads."""
    athlete = _create_athlete(db_session)
    response = client.get(f"/dashboard/load?athlete_id={athlete.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["history"] == []
    assert body["latest"] == {"ctl": 0.0, "atl": 0.0, "tsb": 0.0, "acwr": 1.0}
    assert body["target"] is None
    assert body["training_phase"] == "Base"
```

- [ ] **Step 2: Run tests — first assertion expected to FAIL**

Run: `cd backend && python -m pytest tests/test_routers/test_dashboard.py -v`
Expected: `test_dashboard_load_never_calls_enqueue_backfill` fails because the current `get_load` still calls `enqueue_backfill` when `count < 10`. `test_dashboard_load_returns_empty_history_for_new_athlete` may pass — that's fine; it locks the pure-read contract.

- [ ] **Step 3: Strip the reactive backfill from `get_load`**

In `backend/app/routers/dashboard.py`:

Replace the entire top of the file (imports + `get_load` function) with:

```python
from datetime import date, timedelta

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.metrics import LoadHistory
from app.models.target import Priority, RaceTarget

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
```

Note the removals vs. the current file:
- Dropped `from fastapi import ..., BackgroundTasks`
- Dropped `from sqlalchemy import func` (was only used by `activity_count`)
- Dropped `from app.models.activity import Activity` (ditto)
- Dropped `from app.workers.tasks import enqueue_backfill`

Then replace the `get_load` function (roughly lines 55-72 of the current file) with:

```python
@router.get("/load", response_model=DashboardLoadOut)
async def get_load(
    athlete_id: int,
    db: AsyncSession = Depends(get_db),
) -> DashboardLoadOut:
    history = await load_history(db, athlete_id)
    target = await nearest_a_target(db, athlete_id)
    return DashboardLoadOut(
        training_phase=compute_phase(target.race_date) if target else "Base",
        latest=latest_snapshot(history),
        history=[load_point(row) for row in history],
        weekly_volume=WeeklyVolumeOut(distance_km=0.0, elevation_gain_m=0.0),
        target=target_summary(target),
    )
```

Also delete the `activity_count` helper (around lines 75-79 of the current file). It's now unused.

Leave all other helpers (`load_history`, `nearest_a_target`, `compute_phase`, `latest_snapshot`, `load_point`, `target_summary`, and the Pydantic response models) untouched.

- [ ] **Step 4: Verify nothing else in the codebase references `activity_count` or the removed imports from `dashboard.py`**

Run:
```bash
cd backend && grep -rn "from app.routers.dashboard import activity_count\|dashboard.activity_count" app/ tests/ 2>/dev/null
```
Expected: no results. (The helper was only used inside `dashboard.py` itself.)

- [ ] **Step 5: Run dashboard tests — expect pass**

Run: `cd backend && python -m pytest tests/test_routers/test_dashboard.py -v`
Expected: 2 passed.

- [ ] **Step 6: Run full suite**

Run: `cd backend && python -m pytest tests/ -x -q`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/dashboard.py backend/tests/test_routers/test_dashboard.py
git commit -m "fix: stop auto-triggering backfill from /dashboard/load"
```

---

## Task 4: OAuth callback triggers one-time backfill

**Files:**
- Modify: `backend/app/routers/auth.py`
- Create: `backend/tests/test_routers/test_auth.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_routers/test_auth.py`:

```python
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.routers import auth


FAKE_TOKEN_PAYLOAD = {
    "access_token": "at-123",
    "refresh_token": "rt-123",
    "expires_at": int(datetime.now(timezone.utc).timestamp()) + 3600,
    "athlete": {
        "id": 777,
        "firstname": "Duncan",
        "lastname": "Tester",
        "profile": "https://example.com/avatar.png",
        "city": "Hanoi",
        "country": "Vietnam",
    },
}


def _seed_state(state: str = "test-state") -> str:
    auth._state_store.add(state)
    return state


def test_oauth_callback_fresh_athlete_triggers_backfill(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First-time OAuth connect (no existing athlete) must enqueue exactly
    one backfill."""
    state = _seed_state("state-fresh")

    calls: list[int] = []

    async def fake_enqueue_backfill(athlete_id: int) -> None:
        calls.append(athlete_id)

    monkeypatch.setattr("app.routers.auth.enqueue_backfill", fake_enqueue_backfill)

    async def fake_exchange(code: str) -> dict:
        assert code == "auth-code"
        return FAKE_TOKEN_PAYLOAD

    monkeypatch.setattr("app.routers.auth.exchange_code", fake_exchange)

    response = client.get(
        f"/auth/callback?code=auth-code&state={state}", follow_redirects=False
    )
    assert response.status_code == 302

    # The new athlete should exist in DB with backfilled_at still None
    # (the worker is what sets it — not the callback).
    async def _fetch() -> Athlete:
        result = await db_session.execute(
            select(Athlete).where(Athlete.strava_athlete_id == 777)
        )
        return result.scalar_one()

    athlete = asyncio.run(_fetch())
    assert athlete.backfilled_at is None

    assert calls == [athlete.id], (
        "fresh OAuth connect must schedule exactly one backfill for the new athlete"
    )


def test_oauth_callback_returning_athlete_skips_backfill(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reconnecting an athlete whose backfilled_at is set must NOT fire
    a second backfill."""
    state = _seed_state("state-returning")

    # Pre-create the athlete with backfilled_at populated
    existing = Athlete(
        strava_athlete_id=777,
        backfilled_at=datetime.now(timezone.utc),
    )
    db_session.add(existing)
    asyncio.run(db_session.commit())
    asyncio.run(db_session.refresh(existing))

    calls: list[int] = []

    async def fake_enqueue_backfill(athlete_id: int) -> None:
        calls.append(athlete_id)

    monkeypatch.setattr("app.routers.auth.enqueue_backfill", fake_enqueue_backfill)

    async def fake_exchange(code: str) -> dict:
        return FAKE_TOKEN_PAYLOAD

    monkeypatch.setattr("app.routers.auth.exchange_code", fake_exchange)

    response = client.get(
        f"/auth/callback?code=auth-code&state={state}", follow_redirects=False
    )
    assert response.status_code == 302
    assert calls == [], "already-backfilled athlete must not trigger a backfill"


def test_oauth_callback_existing_athlete_without_backfill_retries(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reconnecting an athlete whose prior backfill failed (backfilled_at
    still None) must retry the backfill."""
    state = _seed_state("state-retry")

    existing = Athlete(
        strava_athlete_id=777,
        backfilled_at=None,
    )
    db_session.add(existing)
    asyncio.run(db_session.commit())
    asyncio.run(db_session.refresh(existing))

    calls: list[int] = []

    async def fake_enqueue_backfill(athlete_id: int) -> None:
        calls.append(athlete_id)

    monkeypatch.setattr("app.routers.auth.enqueue_backfill", fake_enqueue_backfill)

    async def fake_exchange(code: str) -> dict:
        return FAKE_TOKEN_PAYLOAD

    monkeypatch.setattr("app.routers.auth.exchange_code", fake_exchange)

    response = client.get(
        f"/auth/callback?code=auth-code&state={state}", follow_redirects=False
    )
    assert response.status_code == 302
    assert calls == [existing.id], (
        "athlete with null backfilled_at must retry on reconnect"
    )
```

- [ ] **Step 2: Run tests — expect 3 failures**

Run: `cd backend && python -m pytest tests/test_routers/test_auth.py -v`
Expected: all 3 tests fail because the callback doesn't call `enqueue_backfill` yet. (The fresh-athlete test may fail at import too if `app.routers.auth.enqueue_backfill` doesn't exist — that's also expected and will resolve in Step 3.)

- [ ] **Step 3: Wire `enqueue_backfill` into the OAuth callback**

In `backend/app/routers/auth.py`:

Add to the imports block:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, Query
```

(add `BackgroundTasks` alphabetically to the existing `from fastapi import ...` line)

Add near the other `app.services` / `app.models` imports:

```python
from app.workers.tasks import enqueue_backfill
```

Update the `strava_callback` signature and body. Find the existing function (starts at line 35). Replace its signature and the successful-path section with:

```python
@router.get("/callback")
async def strava_callback(
    background_tasks: BackgroundTasks,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if state not in _state_store:
        return RedirectResponse(
            f"{settings.frontend_url}/connect?oauth_error=invalid_state", status_code=302
        )
    _state_store.remove(state)

    try:
        token_data = await exchange_code(code)
        athlete = await upsert_athlete(db, token_data)
        await upsert_credentials(db, athlete.id, token_data)
        await db.commit()
    except StravaOAuthError as exc:
        await db.rollback()
        logger.warning("Strava token exchange failed: %s", exc.message)
        return RedirectResponse(
            f"{settings.frontend_url}/connect?oauth_error=strava_token", status_code=302
        )
    except StravaPayloadError as exc:
        await db.rollback()
        logger.warning("Strava token payload invalid: %s", exc)
        return RedirectResponse(
            f"{settings.frontend_url}/connect?oauth_error=strava_payload", status_code=302
        )
    except TokenServiceError:
        await db.rollback()
        logger.exception("Encrypting Strava tokens failed — check ENCRYPTION_KEY")
        return RedirectResponse(
            f"{settings.frontend_url}/connect?oauth_error=encryption_config", status_code=302
        )
    except Exception:
        await db.rollback()
        logger.exception("OAuth callback failed")
        return RedirectResponse(
            f"{settings.frontend_url}/connect?oauth_error=server_error", status_code=302
        )

    # One-time history backfill: only fires when the athlete has never been
    # backfilled. See docs/superpowers/specs/2026-04-21-webhook-only-ingest-design.md.
    if athlete.backfilled_at is None:
        background_tasks.add_task(enqueue_backfill, athlete.id)

    return RedirectResponse(f"{settings.frontend_url}/setup?athlete_id={athlete.id}")
```

- [ ] **Step 4: Run auth tests — expect pass**

Run: `cd backend && python -m pytest tests/test_routers/test_auth.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run full suite**

Run: `cd backend && python -m pytest tests/ -x -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/auth.py backend/tests/test_routers/test_auth.py
git commit -m "feat: trigger one-time backfill on OAuth callback for fresh athletes"
```

---

## Task 5: End-to-end verification

**Files:**
- No new code. This task is verification + a final integration test that the contract holds end-to-end.
- Create: `backend/tests/test_routers/test_rate_limit_regression.py`

- [ ] **Step 1: Write the regression guard test**

`backend/tests/test_routers/test_rate_limit_regression.py`:

```python
"""Regression guard: the two code paths that historically called Strava
outside the webhook flow must not silently come back.

If these tests fail, someone has re-introduced a rate-limit-burning trigger
— audit before "fixing" them.
"""
from __future__ import annotations

import inspect

from app.routers import auth, dashboard


def test_dashboard_router_has_no_backfill_reference() -> None:
    """dashboard.py must not import or call enqueue_backfill.

    This is the canonical 'polling' path we removed. Re-introducing it
    would mean every dashboard refresh can trigger ~21 Strava reads.
    """
    source = inspect.getsource(dashboard)
    assert "enqueue_backfill" not in source, (
        "dashboard.py must not reference enqueue_backfill — it re-introduces "
        "the dashboard-refresh rate-limit-burn bug. See "
        "docs/superpowers/specs/2026-04-21-webhook-only-ingest-design.md."
    )
    assert "BackgroundTasks" not in source, (
        "dashboard.py must not take a BackgroundTasks parameter — the "
        "endpoint is now a pure DB read. If you need background work on "
        "the dashboard, open a new design doc first."
    )


def test_auth_callback_is_the_only_new_backfill_trigger() -> None:
    """auth.py is the ONLY route that should call enqueue_backfill.

    If any other router starts calling it without a design-doc update,
    flag it here.
    """
    source = inspect.getsource(auth)
    assert "enqueue_backfill" in source, (
        "auth.py must import enqueue_backfill — it's the one-time trigger "
        "point for new-athlete history backfill."
    )
    assert "backfilled_at is None" in source, (
        "auth callback must gate the backfill on backfilled_at being null, "
        "otherwise every OAuth reconnect re-fires a backfill."
    )
```

- [ ] **Step 2: Run the regression test**

Run: `cd backend && python -m pytest tests/test_routers/test_rate_limit_regression.py -v`
Expected: 2 passed.

- [ ] **Step 3: Run the full suite**

Run: `cd backend && python -m pytest tests/ -x -q`
Expected: all green.

- [ ] **Step 4: Manual smoke check (optional, for the developer running this plan)**

With the dev stack running (`docker compose up -d`, backend on :8000, frontend on :5173):

1. Hit `/dashboard/load?athlete_id=<your-id>` directly via curl. Watch backend logs. Confirm no `backfill complete:` or `enqueue_activity` message appears.
2. `curl http://localhost:8000/health` to confirm webhook subscription still registered.
3. If you have credentials, you can also reconnect OAuth through the frontend and watch the backend log for a single `backfill complete: athlete=<id> ingested=<n>` line.

Skip this step if you don't have a live Strava-connected dev environment — the automated tests already lock the behavior.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_routers/test_rate_limit_regression.py
git commit -m "test: dashboard never calls Strava; OAuth backfill is once-per-athlete"
```

---

## Final verification

- [ ] **Backend full suite**

Run: `cd backend && python -m pytest tests/ -x -q`
Expected: green.

- [ ] **Confirm commit history is clean**

Run: `git log main..HEAD --oneline`
Expected (5 new commits on top of the spec commit `1905aaf`):

```
<sha5> test: dashboard never calls Strava; OAuth backfill is once-per-athlete
<sha4> feat: trigger one-time backfill on OAuth callback for fresh athletes
<sha3> fix: stop auto-triggering backfill from /dashboard/load
<sha2> feat: mark athletes.backfilled_at after successful backfill
<sha1> chore: alembic 006 — athletes.backfilled_at column + ORM field
1905aaf docs: spec for webhook-only activity ingest (remove dashboard auto-backfill)
```

---

## Notes for the executor

- **Import consolidation:** Every task says "add to the existing import block." Do not create new top-of-file blocks; merge alphabetically into what's there. Previous features (training-plan-import) established this pattern — follow it.
- **SQLite test DB caveat:** `DateTime(timezone=True)` on SQLite strips tzinfo on readback. Tests that compare `backfilled_at >= before` need the adapter pattern (re-attach `timezone.utc` if tzinfo is None). See `test_backfill_marks_complete.py` for the canonical form.
- **Async fixture decorator:** Use `@pytest_asyncio.fixture`, not `@pytest.fixture`, for any async fixture. This repo is pytest-asyncio strict mode. (See `backend/tests/test_services/test_plan_import_sync.py` for reference.)
- **Worker session lifecycle:** `enqueue_backfill` creates its OWN session inside the worker (`get_session_factory()()`). It does NOT share the session from the OAuth callback. So committing in the worker (to set `backfilled_at`) is safe and can't corrupt the callback's transaction.
- **Existing-user migration behavior:** Existing athletes will have `backfilled_at = NULL` after migration 006. The first OAuth reconnect after deploy will trigger a backfill for them. This is intentional — it populates any gaps from past outages and gives them a known-good baseline. If you (Duncan) don't want this, set `backfilled_at = now()` manually for your athlete row after the migration and before any reconnect.
- **Order matters:** Task 1 (migration + ORM column) must come first — every later task reads or writes `athlete.backfilled_at`. Tasks 2/3/4 are independent of each other (their tests seed `backfilled_at` directly where needed, not via the worker). Task 5 (regression guard) must come last because it inspects the final state of `dashboard.py` and `auth.py`. The order given here (1 → 2 → 3 → 4 → 5) is natural; reordering 2/3/4 is fine if preferred.
