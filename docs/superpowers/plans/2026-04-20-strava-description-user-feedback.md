# Strava description clarity + user feedback loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Strava-pushed activity descriptions scannable on mobile (grouped 3-block layout), add a public 1-tap feedback link (thumb + comment), and surface the feedback stream inside the existing admin dashboard with filters.

**Architecture:** New `user_feedback` table + one public router (`app/routers/feedback.py`) + one admin router (`app/admin/routers/admin_feedback.py`). The pure `format_strava_description()` gains a required `feedback_url` param and a new template with blank-line groups + divider. Frontend adds `/feedback/:activityId` (public, mobile-first, Vietnamese copy) and `/admin/feedback` (timeline with filter chips).

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, pytest + sqlite in-memory for backend; React 18, TanStack Query v5, Tailwind for frontend.

**Spec:** `docs/superpowers/specs/2026-04-20-strava-description-user-feedback-design.md`

---

## File Map

| Action | File |
|---|---|
| **Create** | `backend/migrations/versions/003_user_feedback.py` |
| **Create** | `backend/app/models/feedback.py` |
| Modify | `backend/app/models/__init__.py` |
| **Create** | `backend/app/routers/feedback.py` |
| **Create** | `backend/app/admin/routers/admin_feedback.py` |
| Modify | `backend/app/main.py` |
| Modify | `backend/app/services/description_builder.py` |
| Modify | `backend/app/services/activity_ingestion.py` |
| Modify | `backend/tests/test_services/test_description_builder.py` |
| **Create** | `backend/tests/test_routers/test_feedback.py` |
| **Create** | `backend/tests/test_routers/test_admin_feedback.py` |
| Modify | `frontend/src/types/index.ts` |
| Modify | `frontend/src/api/client.ts` |
| **Create** | `frontend/src/pages/Feedback.tsx` |
| Modify | `frontend/src/App.tsx` |
| Modify | `frontend/src/admin/api.ts` |
| Modify | `frontend/src/admin/types.ts` |
| **Create** | `frontend/src/admin/pages/Feedback.tsx` |
| Modify | `frontend/src/admin/AdminApp.tsx` |
| Modify | `frontend/src/admin/components/AdminNav.tsx` |

---

## Task 1: Alembic migration `003_user_feedback`

**Files:**
- Create: `backend/migrations/versions/003_user_feedback.py`

- [ ] **Step 1: Create the migration file**

```python
"""user_feedback table (thumb + comment from runner, read_at for admin triage).

Revision ID: 003_user_feedback
Revises: 002_admin_dashboard
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "003_user_feedback"
down_revision: Union[str, None] = "002_admin_dashboard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_feedback (
            id SERIAL PRIMARY KEY,
            activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
            athlete_id INTEGER NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
            thumb TEXT NOT NULL CHECK (thumb IN ('up', 'down')),
            comment TEXT,
            read_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_feedback_created ON user_feedback (created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_feedback_activity ON user_feedback (activity_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_feedback_unread ON user_feedback (read_at) "
        "WHERE read_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_feedback_unread")
    op.execute("DROP INDEX IF EXISTS ix_user_feedback_activity")
    op.execute("DROP INDEX IF EXISTS ix_user_feedback_created")
    op.execute("DROP TABLE IF EXISTS user_feedback")
```

- [ ] **Step 2: Commit**

```bash
git add backend/migrations/versions/003_user_feedback.py
git commit -m "feat(db): add user_feedback table migration (003)"
```

---

## Task 2: `UserFeedback` SQLAlchemy model

**Files:**
- Create: `backend/app/models/feedback.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create the model file**

```python
# backend/app/models/feedback.py
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class UserFeedback(Base):
    __tablename__ = "user_feedback"
    __table_args__ = (
        CheckConstraint("thumb IN ('up','down')", name="ck_user_feedback_thumb"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    thumb: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
```

- [ ] **Step 2: Register in models `__init__.py`**

Replace the file with:
```python
# backend/app/models/__init__.py
from app.models.activity import Activity
from app.models.athlete import Athlete, AthleteProfile, Units
from app.models.credentials import StravaCredential
from app.models.feedback import UserFeedback
from app.models.metrics import ActivityMetrics, LoadHistory
from app.models.target import Priority, RaceTarget

__all__ = [
    "Activity",
    "ActivityMetrics",
    "Athlete",
    "AthleteProfile",
    "LoadHistory",
    "Priority",
    "RaceTarget",
    "StravaCredential",
    "Units",
    "UserFeedback",
]
```

- [ ] **Step 3: Run existing tests to confirm no regression**

```bash
cd backend
pytest tests/ -q
```

Expected: same count as before (27 passed) — adding a model does not break anything.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/feedback.py backend/app/models/__init__.py
git commit -m "feat(db): add UserFeedback model + register in package"
```

---

## Task 3: Rewrite description builder for Grouped layout

This is TDD — rewrite the tests first (they will fail), then change the implementation to make them pass.

**Files:**
- Modify: `backend/tests/test_services/test_description_builder.py` (full rewrite)
- Modify: `backend/app/services/description_builder.py`

- [ ] **Step 1: Replace the test file with the new assertions**

```python
# backend/tests/test_services/test_description_builder.py
from app.services.description_builder import acwr_zone_label, format_strava_description


def _full_kwargs(**overrides) -> dict:
    base = dict(
        tss=82.0,
        acwr=1.12,
        z2_pct=68.0,
        hr_drift_pct=4.1,
        decoupling_pct=3.8,
        next_action="90' trail, quad-load descents",
        deep_dive_url="http://app/a/42?athlete_id=1",
        feedback_url="http://app/feedback/42?athlete_id=1",
        nutrition_protocol="60g carb/h, mỗi 20p",
        vmm_projection="vững aerobic, cần nhiều descent hơn",
    )
    base.update(overrides)
    return base


def test_acwr_zone_label_underload() -> None:
    assert acwr_zone_label(0.5) == "underload"
    assert acwr_zone_label(0.79) == "underload"


def test_acwr_zone_label_green() -> None:
    assert acwr_zone_label(0.8) == "green"
    assert acwr_zone_label(1.3) == "green"


def test_acwr_zone_label_caution() -> None:
    assert acwr_zone_label(1.31) == "caution"
    assert acwr_zone_label(1.5) == "caution"


def test_acwr_zone_label_injury_risk() -> None:
    assert acwr_zone_label(1.51) == "injury risk"


def test_metrics_block_has_first_line_with_tss_acwr() -> None:
    result = format_strava_description(**_full_kwargs())
    first_line = result.splitlines()[0]
    assert "TSS 82" in first_line
    assert "ACWR 1.12" in first_line
    assert "green" in first_line


def test_metrics_block_second_line_has_z2_drift_decoupling() -> None:
    result = format_strava_description(**_full_kwargs())
    second_line = result.splitlines()[1]
    assert "Z2 68%" in second_line
    assert "HR drift 4.1%" in second_line
    assert "Decoupling 3.8%" in second_line


def test_coaching_block_present_when_nutrition_and_projection_provided() -> None:
    result = format_strava_description(**_full_kwargs())
    assert "Fuel: 60g carb/h, mỗi 20p" in result
    assert "VMM: vững aerobic, cần nhiều descent hơn" in result


def test_next_line_prefixed_with_arrow() -> None:
    result = format_strava_description(**_full_kwargs(next_action="Easy Z2 60'"))
    assert "→ Next: Easy Z2 60'" in result


def test_divider_and_links_at_bottom() -> None:
    result = format_strava_description(**_full_kwargs())
    lines = result.splitlines()
    divider_idx = next(i for i, ln in enumerate(lines) if set(ln) == {"─"})
    # Divider comes before the two link lines.
    assert "Deep dive" in lines[divider_idx + 1]
    assert "Feedback" in lines[divider_idx + 2]


def test_feedback_url_appears_on_its_own_line() -> None:
    result = format_strava_description(
        **_full_kwargs(feedback_url="http://app/feedback/99?athlete_id=7")
    )
    lines = result.splitlines()
    feedback_line = next(ln for ln in lines if "Feedback" in ln)
    assert "http://app/feedback/99?athlete_id=7" in feedback_line


def test_deep_dive_url_appears_on_its_own_line() -> None:
    result = format_strava_description(**_full_kwargs(deep_dive_url="http://app/a/99"))
    lines = result.splitlines()
    deep_line = next(ln for ln in lines if "Deep dive" in ln)
    assert "http://app/a/99" in deep_line


def test_coaching_block_omitted_when_both_empty_no_double_blank() -> None:
    result = format_strava_description(
        **_full_kwargs(nutrition_protocol="", vmm_projection="")
    )
    assert "Fuel:" not in result
    assert "VMM:" not in result
    assert "\n\n\n" not in result  # never two blank lines in a row


def test_next_line_omitted_when_next_action_empty() -> None:
    result = format_strava_description(**_full_kwargs(next_action=""))
    assert "→ Next:" not in result
    assert "\n\n\n" not in result


def test_tss_rounds_to_int() -> None:
    result = format_strava_description(**_full_kwargs(tss=82.7))
    assert "TSS 83" in result


def test_injury_risk_zone_appears_in_first_line() -> None:
    result = format_strava_description(**_full_kwargs(acwr=1.6))
    first_line = result.splitlines()[0]
    assert "injury risk" in first_line
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend
pytest tests/test_services/test_description_builder.py -v
```

Expected: new tests fail (`feedback_url` is not a parameter yet, divider missing, etc.).

- [ ] **Step 3: Rewrite the description builder**

Replace `backend/app/services/description_builder.py` with:

```python
# backend/app/services/description_builder.py
_DIVIDER = "─" * 17


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
    feedback_url: str,
    nutrition_protocol: str = "",
    vmm_projection: str = "",
) -> str:
    """Build a Strava activity description split into visually distinct blocks.

    Layout:
        metrics (2 lines)
        [blank]
        coaching  (0-2 lines, omitted entirely when both inputs empty)
        [blank]
        → Next:  (omitted when next_action empty)
        [blank]
        ──────
        📊 Deep dive:  <url>
        💬 Feedback:   <url>
    """
    zone = acwr_zone_label(acwr)
    blocks: list[list[str]] = []

    blocks.append([
        f"⚡ TSS {tss:.0f}  ·  ACWR {acwr:.2f} {zone}",
        f"   Z2 {z2_pct:.0f}%  ·  HR drift {hr_drift_pct:.1f}%  ·  Decoupling {decoupling_pct:.1f}%",
    ])

    coaching: list[str] = []
    if nutrition_protocol:
        coaching.append(f"🍜 Fuel: {nutrition_protocol}")
    if vmm_projection:
        coaching.append(f"🏔️ VMM: {vmm_projection}")
    if coaching:
        blocks.append(coaching)

    if next_action:
        blocks.append([f"→ Next: {next_action}"])

    blocks.append([
        _DIVIDER,
        f"📊 Deep dive:  {deep_dive_url}",
        f"💬 Feedback:   {feedback_url}",
    ])

    return "\n\n".join("\n".join(block) for block in blocks)
```

- [ ] **Step 4: Run the tests again to verify they pass**

```bash
cd backend
pytest tests/test_services/test_description_builder.py -v
```

Expected: all 14 tests pass.

- [ ] **Step 5: Run the full test suite to check regressions**

```bash
cd backend
pytest tests/ -q
```

Expected: some tests in `test_services/test_activity_ingestion.py` may fail because callers of `format_strava_description` do not yet pass `feedback_url`. Those are fixed in Task 4. Continue.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/description_builder.py \
  backend/tests/test_services/test_description_builder.py
git commit -m "feat(desc): grouped 3-block Strava description + feedback_url param"
```

---

## Task 4: Wire `feedback_url` through ingestion callers

**Files:**
- Modify: `backend/app/services/activity_ingestion.py`

- [ ] **Step 1: Update `_push_description` to build and pass `feedback_url`**

In `backend/app/services/activity_ingestion.py`, inside `_push_description()`, replace the `description = format_strava_description(...)` call with:

```python
        feedback_url = (
            f"{settings.frontend_url}/feedback/{activity.id}"
            f"?athlete_id={activity.athlete_id}"
        )
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
            feedback_url=feedback_url,
            nutrition_protocol=str(activity.debrief.get("nutrition_protocol", "")),
            vmm_projection=str(activity.debrief.get("vmm_projection", "")),
        )
```

- [ ] **Step 2: Update `push_description_for_activity` similarly**

Inside `push_description_for_activity()`, replace the `description = format_strava_description(...)` block with:

```python
    feedback_url = (
        f"{settings.frontend_url}/feedback/{activity.id}"
        f"?athlete_id={activity.athlete_id}"
    )
    description = format_strava_description(
        tss=metrics.hr_tss or 0.0 if metrics else 0.0,
        acwr=acwr,
        z2_pct=z2_pct,
        hr_drift_pct=metrics.hr_drift_pct or 0.0 if metrics else 0.0,
        decoupling_pct=metrics.aerobic_decoupling_pct or 0.0 if metrics else 0.0,
        next_action=str(activity.debrief.get("next_session_action", "")),
        deep_dive_url=(
            f"{settings.frontend_url}/activities/{activity.id}"
            f"?athlete_id={activity.athlete_id}"
        ),
        feedback_url=feedback_url,
        nutrition_protocol=str(activity.debrief.get("nutrition_protocol", "")),
        vmm_projection=str(activity.debrief.get("vmm_projection", "")),
    )
```

- [ ] **Step 3: Run the full test suite**

```bash
cd backend
pytest tests/ -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/activity_ingestion.py
git commit -m "feat(ingest): pass feedback_url into strava description builder"
```

---

## Task 5: Public `POST /feedback` + `GET /feedback/activity/{id}` — tests first

**Files:**
- Create: `backend/tests/test_routers/test_feedback.py`
- Create: `backend/app/routers/feedback.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_routers/test_feedback.py`:

```python
import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.feedback import UserFeedback


def _seed_athlete_and_activity(db_session: AsyncSession) -> tuple[Athlete, Activity]:
    async def _seed() -> tuple[Athlete, Activity]:
        athlete = Athlete(id=1, strava_athlete_id=1001)
        db_session.add(athlete)
        await db_session.flush()
        activity = Activity(
            id=42,
            athlete_id=1,
            strava_activity_id=9876543210,
            name="Morning Run",
            sport_type="Run",
            processing_status="done",
        )
        db_session.add(activity)
        await db_session.flush()
        return athlete, activity

    return asyncio.run(_seed())


def test_post_feedback_happy_path(client: TestClient, db_session: AsyncSession) -> None:
    _seed_athlete_and_activity(db_session)
    resp = client.post(
        "/feedback",
        json={"activity_id": 42, "athlete_id": 1, "thumb": "up", "comment": "Spot on."},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["thumb"] == "up"
    assert body["comment"] == "Spot on."
    assert "created_at" in body and "id" in body

    rows = asyncio.run(
        db_session.execute(select(UserFeedback).where(UserFeedback.activity_id == 42))
    ).scalars().all()
    assert len(rows) == 1


def test_post_feedback_invalid_thumb_returns_422(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    resp = client.post(
        "/feedback",
        json={"activity_id": 42, "athlete_id": 1, "thumb": "yes"},
    )
    assert resp.status_code == 422


def test_post_feedback_comment_too_long_returns_422(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    resp = client.post(
        "/feedback",
        json={
            "activity_id": 42,
            "athlete_id": 1,
            "thumb": "up",
            "comment": "x" * 2001,
        },
    )
    assert resp.status_code == 422


def test_post_feedback_activity_does_not_belong_to_athlete_returns_404(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    async def _add_other_athlete() -> None:
        db_session.add(Athlete(id=2, strava_athlete_id=1002))
        await db_session.flush()
    asyncio.run(_add_other_athlete())
    resp = client.post(
        "/feedback",
        json={"activity_id": 42, "athlete_id": 2, "thumb": "up"},
    )
    assert resp.status_code == 404


def test_post_feedback_nonexistent_activity_returns_404(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    resp = client.post(
        "/feedback",
        json={"activity_id": 9999, "athlete_id": 1, "thumb": "up"},
    )
    assert resp.status_code == 404


def test_post_feedback_nonexistent_athlete_returns_404(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    resp = client.post(
        "/feedback",
        json={"activity_id": 42, "athlete_id": 9999, "thumb": "up"},
    )
    assert resp.status_code == 404


def test_post_feedback_two_submits_insert_two_rows(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    for comment in ["first", "second"]:
        resp = client.post(
            "/feedback",
            json={"activity_id": 42, "athlete_id": 1, "thumb": "up", "comment": comment},
        )
        assert resp.status_code == 201
    rows = asyncio.run(
        db_session.execute(select(UserFeedback).where(UserFeedback.activity_id == 42))
    ).scalars().all()
    assert len(rows) == 2


def test_get_feedback_activity_no_existing_returns_null(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    resp = client.get("/feedback/activity/42?athlete_id=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["existing"] is None
    assert body["strava_activity_id"] == 9876543210


def test_get_feedback_activity_returns_most_recent(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    client.post("/feedback", json={"activity_id": 42, "athlete_id": 1, "thumb": "up", "comment": "old"})
    client.post("/feedback", json={"activity_id": 42, "athlete_id": 1, "thumb": "down", "comment": "new"})
    resp = client.get("/feedback/activity/42?athlete_id=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["existing"]["thumb"] == "down"
    assert body["existing"]["comment"] == "new"
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
cd backend
pytest tests/test_routers/test_feedback.py -v
```

Expected: all fail with 404 (router not registered) or import errors.

- [ ] **Step 3: Create the router**

Create `backend/app/routers/feedback.py`:

```python
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal

from app.database import get_db
from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.feedback import UserFeedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreateRequest(BaseModel):
    activity_id: int = Field(gt=0)
    athlete_id: int = Field(gt=0)
    thumb: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackItemOut(BaseModel):
    id: int
    thumb: Literal["up", "down"]
    comment: str | None
    created_at: datetime


class ExistingFeedbackResponse(BaseModel):
    existing: FeedbackItemOut | None
    strava_activity_id: int


NOT_FOUND = HTTPException(status_code=404, detail="Activity not found")


async def _activity_owned_by(
    db: AsyncSession, activity_id: int, athlete_id: int
) -> Activity:
    athlete = (
        await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    ).scalar_one_or_none()
    if athlete is None:
        raise NOT_FOUND
    activity = (
        await db.execute(
            select(Activity).where(
                Activity.id == activity_id, Activity.athlete_id == athlete_id
            )
        )
    ).scalar_one_or_none()
    if activity is None:
        raise NOT_FOUND
    return activity


@router.post("", response_model=FeedbackItemOut, status_code=201)
async def submit_feedback(
    payload: FeedbackCreateRequest, db: AsyncSession = Depends(get_db)
) -> FeedbackItemOut:
    await _activity_owned_by(db, payload.activity_id, payload.athlete_id)
    row = UserFeedback(
        activity_id=payload.activity_id,
        athlete_id=payload.athlete_id,
        thumb=payload.thumb,
        comment=(payload.comment or "").strip() or None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return FeedbackItemOut(
        id=row.id, thumb=row.thumb, comment=row.comment, created_at=row.created_at  # type: ignore[arg-type]
    )


@router.get("/activity/{activity_id}", response_model=ExistingFeedbackResponse)
async def get_existing_feedback(
    activity_id: int, athlete_id: int, db: AsyncSession = Depends(get_db)
) -> ExistingFeedbackResponse:
    activity = await _activity_owned_by(db, activity_id, athlete_id)
    row = (
        await db.execute(
            select(UserFeedback)
            .where(
                UserFeedback.activity_id == activity_id,
                UserFeedback.athlete_id == athlete_id,
            )
            .order_by(UserFeedback.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    existing = (
        FeedbackItemOut(
            id=row.id, thumb=row.thumb, comment=row.comment, created_at=row.created_at  # type: ignore[arg-type]
        )
        if row is not None
        else None
    )
    return ExistingFeedbackResponse(
        existing=existing, strava_activity_id=activity.strava_activity_id
    )
```

- [ ] **Step 4: Register the router in `app/main.py`**

In `backend/app/main.py`, update the imports and `register_routes()`:

```python
from app.routers import (
    activities, athletes, auth, dashboard, feedback, onboarding, targets, webhook,
)
```

Add one line inside `register_routes()`:

```python
    api.include_router(feedback.router)
```

- [ ] **Step 5: Run the tests**

```bash
cd backend
pytest tests/test_routers/test_feedback.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/feedback.py backend/app/main.py \
  backend/tests/test_routers/test_feedback.py
git commit -m "feat(api): POST /feedback + GET /feedback/activity/{id}"
```

---

## Task 6: Admin feedback endpoints — tests first

**Files:**
- Create: `backend/tests/test_routers/test_admin_feedback.py`
- Create: `backend/app/admin/routers/admin_feedback.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_routers/test_admin_feedback.py`:

```python
import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import auth as admin_auth
from app.admin.models import Admin
from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.feedback import UserFeedback


def _seed_world(db_session: AsyncSession) -> None:
    async def _seed() -> None:
        db_session.add(Admin(
            id=1, email="admin@example.com",
            password_hash=admin_auth.hash_password("pw"), name="Admin",
        ))
        db_session.add(Athlete(id=10, strava_athlete_id=1001))
        db_session.add(Athlete(id=11, strava_athlete_id=1002))
        await db_session.flush()
        db_session.add(Activity(
            id=100, athlete_id=10, strava_activity_id=9_000_000_001,
            name="Morning Run", sport_type="Run", processing_status="done",
        ))
        db_session.add(Activity(
            id=101, athlete_id=11, strava_activity_id=9_000_000_002,
            name="Trail 22k", sport_type="TrailRun", processing_status="done",
        ))
        await db_session.flush()
        db_session.add_all([
            UserFeedback(id=1, activity_id=100, athlete_id=10, thumb="down", comment="Not actionable."),
            UserFeedback(id=2, activity_id=101, athlete_id=11, thumb="up"),
            UserFeedback(id=3, activity_id=100, athlete_id=10, thumb="up", comment="Better."),
        ])
        await db_session.flush()
    asyncio.run(_seed())


def _login(client: TestClient) -> None:
    resp = client.post(
        "/admin/auth/login",
        json={"email": "admin@example.com", "password": "pw"},
    )
    assert resp.status_code == 200


def test_admin_feedback_requires_auth(client: TestClient, db_session: AsyncSession) -> None:
    _seed_world(db_session)
    resp = client.get("/admin/feedback")
    assert resp.status_code == 401


def test_admin_feedback_list_all(client: TestClient, db_session: AsyncSession) -> None:
    _seed_world(db_session)
    _login(client)
    resp = client.get("/admin/feedback")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3
    assert [i["id"] for i in body["items"]] == [3, 2, 1]
    assert body["next_cursor"] is None
    first = body["items"][0]
    assert first["activity_name"] == "Morning Run"
    assert first["athlete_id"] == 10


def test_admin_feedback_filter_down(client: TestClient, db_session: AsyncSession) -> None:
    _seed_world(db_session)
    _login(client)
    resp = client.get("/admin/feedback?thumb=down")
    assert resp.status_code == 200
    body = resp.json()
    assert [i["id"] for i in body["items"]] == [1]


def test_admin_feedback_filter_unread(client: TestClient, db_session: AsyncSession) -> None:
    _seed_world(db_session)
    _login(client)
    resp = client.get("/admin/feedback?unread=true")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 3


def test_admin_feedback_cursor_pagination(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_world(db_session)
    # Seed enough to force a second page (>20 rows).
    async def _more() -> None:
        for i in range(4, 25):
            db_session.add(UserFeedback(
                id=i, activity_id=100, athlete_id=10, thumb="up",
            ))
        await db_session.flush()
    asyncio.run(_more())
    _login(client)
    page1 = client.get("/admin/feedback").json()
    assert len(page1["items"]) == 20
    assert page1["next_cursor"] is not None
    page2 = client.get(f"/admin/feedback?cursor={page1['next_cursor']}").json()
    assert len(page2["items"]) == 4
    assert page2["next_cursor"] is None


def test_admin_feedback_counts(client: TestClient, db_session: AsyncSession) -> None:
    _seed_world(db_session)
    _login(client)
    resp = client.get("/admin/feedback/counts")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"all": 3, "up": 2, "down": 1, "unread": 3}


def test_admin_feedback_mark_read(client: TestClient, db_session: AsyncSession) -> None:
    _seed_world(db_session)
    _login(client)
    resp = client.patch("/admin/feedback/1/read")
    assert resp.status_code == 204
    # Idempotent.
    resp2 = client.patch("/admin/feedback/1/read")
    assert resp2.status_code == 204
    counts = client.get("/admin/feedback/counts").json()
    assert counts["unread"] == 2
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
cd backend
pytest tests/test_routers/test_admin_feedback.py -v
```

Expected: all fail — router not registered.

- [ ] **Step 3: Create the admin router**

Create `backend/app/admin/routers/admin_feedback.py`:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal

from app.admin import auth as admin_auth
from app.admin.models import Admin
from app.database import get_db
from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.feedback import UserFeedback

router = APIRouter(prefix="/admin/feedback", tags=["admin-feedback"])

PAGE_SIZE = 20


class AdminFeedbackItem(BaseModel):
    id: int
    thumb: Literal["up", "down"]
    comment: str | None
    created_at: datetime
    read_at: datetime | None
    activity_id: int
    activity_name: str
    athlete_id: int
    athlete_name: str


class AdminFeedbackPage(BaseModel):
    items: list[AdminFeedbackItem]
    next_cursor: int | None


class AdminFeedbackCounts(BaseModel):
    all: int
    up: int
    down: int
    unread: int


def _athlete_display_name(athlete: Athlete) -> str:
    parts = [p for p in (athlete.firstname, athlete.lastname) if p]
    if parts:
        return " ".join(parts).strip()
    return f"athlete-{athlete.id}"


@router.get("", response_model=AdminFeedbackPage)
async def list_feedback(
    thumb: Literal["up", "down"] | None = None,
    unread: bool = False,
    cursor: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(admin_auth.require_admin),
) -> AdminFeedbackPage:
    stmt = (
        select(UserFeedback, Activity, Athlete)
        .join(Activity, Activity.id == UserFeedback.activity_id)
        .join(Athlete, Athlete.id == UserFeedback.athlete_id)
        .order_by(UserFeedback.id.desc())
        .limit(PAGE_SIZE)
    )
    if thumb is not None:
        stmt = stmt.where(UserFeedback.thumb == thumb)
    if unread:
        stmt = stmt.where(UserFeedback.read_at.is_(None))
    if cursor is not None:
        stmt = stmt.where(UserFeedback.id < cursor)

    rows = (await db.execute(stmt)).all()
    items = [
        AdminFeedbackItem(
            id=fb.id,
            thumb=fb.thumb,  # type: ignore[arg-type]
            comment=fb.comment,
            created_at=fb.created_at,
            read_at=fb.read_at,
            activity_id=activity.id,
            activity_name=activity.name or "Untitled activity",
            athlete_id=athlete.id,
            athlete_name=_athlete_display_name(athlete),
        )
        for fb, activity, athlete in rows
    ]
    next_cursor = items[-1].id if len(items) == PAGE_SIZE else None
    return AdminFeedbackPage(items=items, next_cursor=next_cursor)


@router.get("/counts", response_model=AdminFeedbackCounts)
async def feedback_counts(
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(admin_auth.require_admin),
) -> AdminFeedbackCounts:
    stmt = select(
        func.count(UserFeedback.id),
        func.count(case((UserFeedback.thumb == "up", 1))),
        func.count(case((UserFeedback.thumb == "down", 1))),
        func.count(case((UserFeedback.read_at.is_(None), 1))),
    )
    row = (await db.execute(stmt)).one()
    return AdminFeedbackCounts(all=row[0], up=row[1], down=row[2], unread=row[3])


@router.patch("/{feedback_id}/read", status_code=204)
async def mark_feedback_read(
    feedback_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(admin_auth.require_admin),
) -> Response:
    row = await db.get(UserFeedback, feedback_id)
    if row is not None and row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        await db.commit()
    return Response(status_code=204)
```

- [ ] **Step 4: Register the router in `app/main.py`**

In `backend/app/main.py`:

```python
from app.admin.routers import admin_auth, admin_feedback
```

Inside `register_routes()`:

```python
    api.include_router(admin_feedback.router)
```

- [ ] **Step 5: Run the tests**

```bash
cd backend
pytest tests/test_routers/test_admin_feedback.py -v
```

Expected: all 7 tests pass. Note the tests seed `Athlete(id=10, ...)` without `firstname`/`lastname`, so `athlete_name` is the fallback `athlete-10` / `athlete-11` — the tests do not assert on `athlete_name` values for this reason.

- [ ] **Step 6: Full suite sanity check**

```bash
cd backend
pytest tests/ -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/admin/routers/admin_feedback.py backend/app/main.py \
  backend/tests/test_routers/test_admin_feedback.py
git commit -m "feat(api): admin feedback list/counts/read endpoints"
```

---

## Task 7: Frontend types + API client functions

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add types**

Append to `frontend/src/types/index.ts`:

```ts
export type FeedbackThumb = "up" | "down"

export interface FeedbackItem {
  id: number
  thumb: FeedbackThumb
  comment: string | null
  created_at: string
}

export interface FeedbackCreateRequest {
  activity_id: number
  athlete_id: number
  thumb: FeedbackThumb
  comment?: string
}

export interface ExistingFeedbackResponse {
  existing: FeedbackItem | null
  strava_activity_id: number
}
```

- [ ] **Step 2: Add API client functions**

Append to `frontend/src/api/client.ts`, after `deleteRaceTarget`:

```ts
import type {
  ExistingFeedbackResponse,
  FeedbackCreateRequest,
  FeedbackItem,
} from "../types"

export async function getExistingFeedback(
  activityId: number,
  athleteId: number,
): Promise<ExistingFeedbackResponse> {
  return request(api.get(`/feedback/activity/${activityId}?athlete_id=${athleteId}`))
}

export async function submitFeedback(
  payload: FeedbackCreateRequest,
): Promise<FeedbackItem> {
  return request(api.post("/feedback", payload))
}
```

Make sure the `import type` line is merged into the existing import block (do not duplicate top-level imports).

- [ ] **Step 3: Typecheck**

```bash
cd frontend
npm run typecheck
```

Expected: passes.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/client.ts
git commit -m "feat(fe): types + client fns for user feedback"
```

---

## Task 8: Public `/feedback/:activityId` page

**Files:**
- Create: `frontend/src/pages/Feedback.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/src/pages/Feedback.tsx`:

```tsx
import { useMutation, useQuery } from "@tanstack/react-query"
import { useEffect, useMemo, useState } from "react"
import { useParams, useSearchParams } from "react-router-dom"
import { getExistingFeedback, submitFeedback } from "../api/client"
import type { FeedbackThumb } from "../types"

type Status = "idle" | "submitting" | "submitted" | "error"

export default function Feedback() {
  const activityId = useActivityId()
  const athleteId = useAthleteId()
  if (activityId === null || athleteId === null) return <MissingParams />
  return <FeedbackForm activityId={activityId} athleteId={athleteId} />
}

function FeedbackForm(props: { activityId: number; athleteId: number }) {
  const { activityId, athleteId } = props
  const existingQuery = useQuery({
    queryKey: ["feedback", "existing", activityId, athleteId],
    queryFn: () => getExistingFeedback(activityId, athleteId),
  })
  const mutation = useMutation({
    mutationFn: submitFeedback,
  })
  const [thumb, setThumb] = useState<FeedbackThumb | null>(null)
  const [comment, setComment] = useState("")
  const [status, setStatus] = useState<Status>("idle")

  useEffect(() => {
    if (existingQuery.data?.existing) setStatus("submitted")
  }, [existingQuery.data?.existing])

  const stravaActivityId = existingQuery.data?.strava_activity_id

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (thumb === null || status === "submitting") return
    setStatus("submitting")
    try {
      await mutation.mutateAsync({
        activity_id: activityId,
        athlete_id: athleteId,
        thumb,
        comment: comment.trim() || undefined,
      })
      setStatus("submitted")
    } catch {
      setStatus("error")
    }
  }

  if (existingQuery.isPending) {
    return <Shell><p className="text-sm text-slate-500">Đang tải…</p></Shell>
  }

  if (status === "submitted") {
    return (
      <Shell>
        <div className="text-center">
          <div className="mb-2 text-4xl">💚</div>
          <h1 className="text-xl font-semibold">Nhận rồi — cảm ơn anh!</h1>
          <p className="mt-2 text-sm text-slate-600">
            Phản hồi của anh giúp tụi mình chỉnh debrief tốt hơn cho lần sau.
          </p>
          {stravaActivityId !== undefined && (
            <BackToStrava stravaActivityId={stravaActivityId} />
          )}
        </div>
      </Shell>
    )
  }

  return (
    <Shell>
      <div className="mb-1 text-3xl">👋</div>
      <h1 className="text-lg font-semibold leading-snug">
        Debrief này giúp được anh bao nhiêu?
      </h1>
      <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">
        Tụi mình đang học cách viết debrief tốt hơn — mọi góc nhìn đều quý.
      </p>

      <form onSubmit={onSubmit} className="mt-5 space-y-4">
        <div className="flex gap-3">
          <ThumbButton
            label="👍"
            active={thumb === "up"}
            onClick={() => setThumb("up")}
          />
          <ThumbButton
            label="👎"
            active={thumb === "down"}
            onClick={() => setThumb("down")}
          />
        </div>

        <div>
          <label className="text-xs font-medium text-slate-600">
            Chia sẻ thêm (không bắt buộc)
          </label>
          <textarea
            className="mt-1.5 w-full rounded-lg border border-stone-200 bg-white p-3 text-sm focus:border-orange-400 focus:outline-none focus:ring-1 focus:ring-orange-200"
            rows={3}
            maxLength={2000}
            placeholder="VD: Next-action không thực tế với lịch của em..."
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            disabled={status === "submitting"}
          />
        </div>

        <button
          type="submit"
          disabled={thumb === null || status === "submitting"}
          className="w-full rounded-lg bg-slate-900 py-3 text-sm font-semibold text-white transition disabled:opacity-40"
        >
          {status === "submitting" ? "Đang gửi…" : "Gửi phản hồi"}
        </button>

        {status === "error" && (
          <p className="text-center text-sm text-red-600">
            Có lỗi xảy ra, anh thử lại giúp em nhé.
          </p>
        )}

        <p className="pt-1 text-center text-xs text-slate-400">
          Cảm ơn anh — đọc từng chữ.
        </p>
      </form>
    </Shell>
  )
}

function Shell(props: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-stone-50 px-4 py-8">
      <div className="mx-auto max-w-md rounded-2xl bg-white p-6 shadow-sm">
        {props.children}
      </div>
    </main>
  )
}

function ThumbButton(props: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className={
        "flex-1 rounded-xl border-2 py-4 text-2xl transition " +
        (props.active
          ? "border-orange-500 bg-orange-50"
          : "border-stone-200 bg-white hover:border-stone-300")
      }
      aria-pressed={props.active}
    >
      {props.label}
    </button>
  )
}

function BackToStrava(props: { stravaActivityId: number }) {
  const webUrl = `https://www.strava.com/activities/${props.stravaActivityId}`
  const deepLink = `strava://activities/${props.stravaActivityId}`
  return (
    <a
      href={deepLink}
      onClick={(event) => {
        event.preventDefault()
        // Try the app; fall back to web if not intercepted within 600ms.
        window.location.href = deepLink
        window.setTimeout(() => {
          window.location.href = webUrl
        }, 600)
      }}
      className="mt-5 inline-block rounded-lg bg-orange-500 px-5 py-2.5 text-sm font-semibold text-white"
    >
      Quay lại Strava
    </a>
  )
}

function MissingParams() {
  return (
    <main className="min-h-screen bg-stone-50 px-4 py-8">
      <div className="mx-auto max-w-md rounded-2xl bg-white p-6 shadow-sm">
        <p className="text-sm text-slate-600">
          Link không hợp lệ. Anh mở lại từ activity trên Strava giúp em nhé.
        </p>
      </div>
    </main>
  )
}

function useActivityId(): number | null {
  const params = useParams<{ activityId: string }>()
  const parsed = Number(params.activityId)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function useAthleteId(): number | null {
  const [params] = useSearchParams()
  const raw = params.get("athlete_id")
  const parsed = useMemo(() => (raw === null ? NaN : Number(raw)), [raw])
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}
```

- [ ] **Step 2: Register the route**

Edit `frontend/src/App.tsx`. Add one import:

```tsx
import Feedback from "./pages/Feedback"
```

Add one `<Route>` inside `<Routes>`:

```tsx
          <Route path="/feedback/:activityId" element={<Feedback />} />
```

- [ ] **Step 3: Typecheck and dev-server smoke**

```bash
cd frontend
npm run typecheck
npm run build
```

Expected: both succeed.

- [ ] **Step 4: Manual browser check**

Start backend + frontend. Seed one activity + athlete (via existing flows). Open:
`http://localhost:5173/feedback/<activityId>?athlete_id=<athleteId>`.

Confirm: form renders centered, thumbs toggle, submit disabled until a thumb is chosen, submit succeeds, submitted state shows, reloading the page shows the submitted state directly.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Feedback.tsx frontend/src/App.tsx
git commit -m "feat(fe): public feedback page at /feedback/:activityId"
```

---

## Task 9: Admin feedback API hooks + types

**Files:**
- Modify: `frontend/src/admin/types.ts`
- Modify: `frontend/src/admin/api.ts`

- [ ] **Step 1: Add types**

Append to `frontend/src/admin/types.ts`:

```ts
export interface AdminFeedbackItem {
  id: number
  thumb: "up" | "down"
  comment: string | null
  created_at: string
  read_at: string | null
  activity_id: number
  activity_name: string
  athlete_id: number
  athlete_name: string
}

export interface AdminFeedbackPage {
  items: AdminFeedbackItem[]
  next_cursor: number | null
}

export interface AdminFeedbackCounts {
  all: number
  up: number
  down: number
  unread: number
}

export type AdminFeedbackFilter = "all" | "up" | "down" | "unread"
```

- [ ] **Step 2: Add hooks**

Append to `frontend/src/admin/api.ts`, after `useAdminChangePassword`:

```ts
import type {
  AdminFeedbackCounts,
  AdminFeedbackFilter,
  AdminFeedbackItem,
  AdminFeedbackPage,
} from "./types"
import { useInfiniteQuery } from "@tanstack/react-query"

export const adminFeedbackKeys = {
  list: (filter: AdminFeedbackFilter) => ["admin", "feedback", "list", filter] as const,
  counts: ["admin", "feedback", "counts"] as const,
}

function buildListQuery(filter: AdminFeedbackFilter, cursor: number | null): string {
  const params = new URLSearchParams()
  if (filter === "up" || filter === "down") params.set("thumb", filter)
  if (filter === "unread") params.set("unread", "true")
  if (cursor !== null) params.set("cursor", String(cursor))
  const qs = params.toString()
  return qs ? `/admin/feedback?${qs}` : "/admin/feedback"
}

export function useAdminFeedbackList(filter: AdminFeedbackFilter) {
  return useInfiniteQuery<AdminFeedbackPage, AxiosError>({
    queryKey: adminFeedbackKeys.list(filter),
    initialPageParam: null as number | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await adminHttp.get<AdminFeedbackPage>(
        buildListQuery(filter, pageParam as number | null),
      )
      return data
    },
    getNextPageParam: (last) => last.next_cursor,
  })
}

export function useAdminFeedbackCounts() {
  return useQuery<AdminFeedbackCounts, AxiosError>({
    queryKey: adminFeedbackKeys.counts,
    queryFn: async () => {
      const { data } = await adminHttp.get<AdminFeedbackCounts>("/admin/feedback/counts")
      return data
    },
    staleTime: 30_000,
  })
}

export function useMarkFeedbackRead() {
  const qc = useQueryClient()
  return useMutation<void, AxiosError, number>({
    mutationFn: async (feedbackId) => {
      await adminHttp.patch(`/admin/feedback/${feedbackId}/read`)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminFeedbackKeys.counts })
      qc.invalidateQueries({ queryKey: ["admin", "feedback", "list"] })
    },
  })
}
```

Make sure the `useInfiniteQuery` import merges cleanly into the existing `@tanstack/react-query` import at the top of the file — the final combined import should read:

```ts
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
```

And similarly merge the `import type` block for `./types`.

Separately, `AdminFeedbackItem` is exported from `./types` for consumers. Re-export it from `./api.ts` to keep imports tidy:

```ts
export type { AdminFeedbackItem }
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend
npm run typecheck
```

Expected: passes.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/admin/types.ts frontend/src/admin/api.ts
git commit -m "feat(fe-admin): hooks + types for admin feedback"
```

---

## Task 10: Admin feedback list page

**Files:**
- Create: `frontend/src/admin/pages/Feedback.tsx`
- Modify: `frontend/src/admin/AdminApp.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/src/admin/pages/Feedback.tsx`:

```tsx
import { useState } from "react"
import {
  useAdminFeedbackCounts,
  useAdminFeedbackList,
  useMarkFeedbackRead,
} from "../api"
import type { AdminFeedbackFilter, AdminFeedbackItem } from "../types"

export default function FeedbackPage() {
  const [filter, setFilter] = useState<AdminFeedbackFilter>("all")
  const counts = useAdminFeedbackCounts()
  const list = useAdminFeedbackList(filter)
  const markRead = useMarkFeedbackRead()

  return (
    <div className="p-6">
      <h1 className="mb-4 text-2xl font-semibold">Phản hồi từ runner</h1>

      <div className="mb-6 flex flex-wrap gap-2">
        <Chip
          label={`Tất cả ${counts.data?.all ?? 0}`}
          active={filter === "all"}
          onClick={() => setFilter("all")}
        />
        <Chip
          label={`👎 ${counts.data?.down ?? 0}`}
          active={filter === "down"}
          onClick={() => setFilter("down")}
        />
        <Chip
          label={`👍 ${counts.data?.up ?? 0}`}
          active={filter === "up"}
          onClick={() => setFilter("up")}
        />
        <Chip
          label={`Chưa đọc ${counts.data?.unread ?? 0}`}
          active={filter === "unread"}
          onClick={() => setFilter("unread")}
        />
      </div>

      {list.isPending && <Skeleton />}
      {list.isError && (
        <ErrorBanner onRetry={() => list.refetch()} />
      )}
      {list.data && (
        <>
          {list.data.pages.flatMap((page) => page.items).length === 0 ? (
            <p className="text-sm text-slate-500">Chưa có phản hồi nào.</p>
          ) : (
            <ul className="space-y-3">
              {list.data.pages.flatMap((page) => page.items).map((item) => (
                <FeedbackCard
                  key={item.id}
                  item={item}
                  onRead={() => markRead.mutate(item.id)}
                />
              ))}
            </ul>
          )}
          {list.hasNextPage && (
            <button
              onClick={() => list.fetchNextPage()}
              disabled={list.isFetchingNextPage}
              className="mt-4 rounded border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50"
            >
              {list.isFetchingNextPage ? "Đang tải…" : "Tải thêm"}
            </button>
          )}
        </>
      )}
    </div>
  )
}

function Chip(props: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={props.onClick}
      className={
        "rounded-full px-3 py-1.5 text-sm transition " +
        (props.active
          ? "bg-slate-900 text-white"
          : "bg-slate-100 text-slate-700 hover:bg-slate-200")
      }
    >
      {props.label}
    </button>
  )
}

function FeedbackCard(props: { item: AdminFeedbackItem; onRead: () => void }) {
  const { item } = props
  const unread = item.read_at === null
  return (
    <li
      onClick={() => {
        if (unread) props.onRead()
      }}
      className={
        "cursor-pointer rounded-lg border p-4 transition " +
        (unread
          ? "border-orange-200 bg-orange-50/50 hover:bg-orange-50"
          : "border-slate-200 bg-white hover:bg-slate-50")
      }
    >
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-base">{item.thumb === "up" ? "👍" : "👎"}</span>
        <span className="font-semibold">{item.athlete_name}</span>
        <span className="text-slate-400">·</span>
        <span className="text-slate-700">{item.activity_name}</span>
        <span className="text-slate-400">·</span>
        <span className="text-slate-500">{relativeTime(item.created_at)}</span>
        {unread && <UnreadDot />}
        <a
          href={`/activities/${item.activity_id}?athlete_id=${item.athlete_id}`}
          target="_blank"
          rel="noreferrer"
          onClick={(event) => event.stopPropagation()}
          className="ml-auto text-sm text-blue-600 hover:underline"
        >
          Mở activity →
        </a>
      </div>
      {item.comment ? (
        <p className="whitespace-pre-wrap text-sm text-slate-700">{item.comment}</p>
      ) : (
        <p className="text-sm italic text-slate-400">(không có comment)</p>
      )}
    </li>
  )
}

function UnreadDot() {
  return (
    <span
      aria-label="chưa đọc"
      className="ml-1 inline-block h-2 w-2 rounded-full bg-orange-500"
    />
  )
}

function Skeleton() {
  return (
    <ul className="space-y-3">
      {[0, 1, 2].map((i) => (
        <li key={i} className="h-24 animate-pulse rounded-lg bg-slate-100" />
      ))}
    </ul>
  )
}

function ErrorBanner(props: { onRetry: () => void }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      <p>Không tải được danh sách phản hồi.</p>
      <button
        onClick={props.onRetry}
        className="mt-2 rounded border border-red-300 px-3 py-1 text-xs hover:bg-red-100"
      >
        Tải lại
      </button>
    </div>
  )
}

function relativeTime(iso: string): string {
  const date = new Date(iso)
  const diffSec = Math.floor((Date.now() - date.getTime()) / 1000)
  if (diffSec < 60) return "vừa xong"
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}p trước`
  if (diffSec < 86_400) return `${Math.floor(diffSec / 3600)}h trước`
  return `${Math.floor(diffSec / 86_400)}d trước`
}
```

- [ ] **Step 2: Register the route in `AdminApp.tsx`**

Edit `frontend/src/admin/AdminApp.tsx`:

```tsx
import { Route, Routes } from "react-router-dom"
import AdminNav from "./components/AdminNav"
import RequireAdmin from "./components/RequireAdmin"
import Feedback from "./pages/Feedback"
import Home from "./pages/Home"
import Login from "./pages/Login"

function Protected({ children }: { children: React.ReactNode }) {
  return (
    <RequireAdmin>
      <div className="min-h-screen bg-white">
        <AdminNav />
        {children}
      </div>
    </RequireAdmin>
  )
}

export default function AdminApp() {
  return (
    <Routes>
      <Route path="login" element={<Login />} />
      <Route path="feedback" element={<Protected><Feedback /></Protected>} />
      <Route path="" element={<Protected><Home /></Protected>} />
      <Route path="*" element={<Protected><Home /></Protected>} />
    </Routes>
  )
}
```

- [ ] **Step 3: Typecheck + build**

```bash
cd frontend
npm run typecheck
npm run build
```

Expected: both pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/admin/pages/Feedback.tsx frontend/src/admin/AdminApp.tsx
git commit -m "feat(fe-admin): feedback timeline page with filter chips"
```

---

## Task 11: Admin nav link with unread badge

**Files:**
- Modify: `frontend/src/admin/components/AdminNav.tsx`

- [ ] **Step 1: Update the nav**

Replace `frontend/src/admin/components/AdminNav.tsx` with:

```tsx
import { Link, useNavigate } from "react-router-dom"
import { useAdminFeedbackCounts, useAdminLogout, useAdminMe } from "../api"

export default function AdminNav() {
  const { data } = useAdminMe()
  const counts = useAdminFeedbackCounts()
  const logout = useAdminLogout()
  const navigate = useNavigate()

  async function handleLogout() {
    try {
      await logout.mutateAsync()
    } catch {
      // Session may still be alive server-side, but the user clicked logout.
      // We navigate to login anyway — the session will expire on its own.
    }
    navigate("/admin/login", { replace: true })
  }

  const unread = counts.data?.unread ?? 0

  return (
    <nav className="flex h-14 items-center justify-between border-b border-slate-200 px-6">
      <div className="flex items-center gap-6">
        <span className="font-semibold">Admin</span>
        <Link to="/admin" className="text-sm text-slate-700 hover:text-slate-900">
          Home
        </Link>
        <Link
          to="/admin/feedback"
          className="relative text-sm text-slate-700 hover:text-slate-900"
        >
          Feedback
          {unread > 0 && (
            <span className="ml-1.5 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-orange-500 px-1.5 text-xs font-semibold text-white">
              {unread}
            </span>
          )}
        </Link>
        <span className="text-sm text-slate-400">Users</span>
        <span className="text-sm text-slate-400">Prompts</span>
        <span className="text-sm text-slate-400">Debriefs</span>
      </div>
      <div className="flex items-center gap-4 text-sm text-slate-600">
        <span>{data?.name ?? data?.email}</span>
        <button
          onClick={handleLogout}
          className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100"
        >
          Logout
        </button>
      </div>
    </nav>
  )
}
```

- [ ] **Step 2: Typecheck + build**

```bash
cd frontend
npm run typecheck
npm run build
```

Expected: both pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/admin/components/AdminNav.tsx
git commit -m "feat(fe-admin): feedback nav link with unread badge"
```

---

## Task 12: End-to-end verification

**Files:** none — manual verification only.

- [ ] **Step 1: Apply the migration against the local database**

```bash
cd backend
alembic upgrade head
```

Expected: migration `003_user_feedback` runs successfully. Check the table exists:

```bash
psql postgresql://postgres:postgres@localhost:5432/stravacoach \
  -c "\d user_feedback"
```

- [ ] **Step 2: Start backend + frontend**

Two terminals:

```bash
# terminal 1
cd backend && uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend && npm run dev
```

- [ ] **Step 3: Public feedback round-trip**

Using an existing seeded athlete (id 1) and activity (id you pick from DB), open:

```
http://localhost:5173/feedback/<activityId>?athlete_id=1
```

Resize window to 390px wide. Confirm:
- Form centered, single card, warm tone, no horizontal scroll.
- Thumbs toggle selected state (orange border).
- Submit disabled until a thumb is chosen.
- Submit succeeds; submitted state replaces the form.
- Reloading the page shows the submitted state immediately (no flicker of the form).

- [ ] **Step 4: Admin view round-trip**

Log in to `/admin` with a seeded admin. Click the new "Feedback" nav link (should show `1` unread badge). Confirm:
- Timeline renders with the feedback just submitted.
- Unread dot visible; clicking the card (not the "Mở activity" link) dismisses the dot and decrements the unread badge.
- Filter chips switch the list correctly.

- [ ] **Step 5: Description push round-trip (if `STRAVA_PUSH_DESCRIPTION=true`)**

With the env flag set, trigger a manual push:

```bash
curl -XPOST http://localhost:8000/activities/<activityId>/push-description
```

Open the activity on Strava and confirm:
- 3 visible groups (metrics / coaching / links).
- Divider line visible.
- "💬 Feedback:" line present, URL clickable.

- [ ] **Step 6: Run the full backend test suite one last time**

```bash
cd backend
pytest tests/ -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit a short verification log if anything was tweaked, then open the PR**

If manual testing required any adjustments, commit them separately. Then:

```bash
git push -u origin feat/user-feedback
gh pr create \
  --title "feat: grouped Strava description + user feedback loop" \
  --body "$(cat <<'EOF'
## Summary
- Strava description now renders in 3 visually distinct blocks with a divider.
- New public `/feedback/:activityId` page (mobile-first, Vietnamese copy).
- New admin `/admin/feedback` timeline with filter chips + unread badge.
- `user_feedback` table + migration 003.

Spec: `docs/superpowers/specs/2026-04-20-strava-description-user-feedback-design.md`

## Test plan
- [ ] `pytest backend/tests/ -q` passes
- [ ] `npm run typecheck && npm run build` in `frontend/`
- [ ] Manual: submit feedback at /feedback/:id?athlete_id=N on a 390px viewport
- [ ] Manual: admin timeline shows the row, mark-read clears the unread badge
- [ ] Manual: pushed Strava description has the new layout + feedback link
EOF
)"
```

---

## Self-Review Checklist

Spec coverage audit:

- Grouped 3-block description layout → Task 3.
- `feedback_url` param threaded through callers → Task 4.
- `user_feedback` table + model + migration → Tasks 1–2.
- Public `POST /feedback`, `GET /feedback/activity/{id}` + validation + 404 leak-prevention → Task 5.
- Admin list, counts, mark-read → Task 6.
- Public feedback page (warm tone, mobile-first, Vietnamese) with idle/submitting/submitted/error states + back-to-Strava deep link → Task 8.
- Admin timeline with chip filters, unread dot, load-more → Task 10.
- Admin nav link with unread badge → Task 11.
- End-to-end smoke test → Task 12.
- Tests for all backend changes → Tasks 3, 5, 6.

Placeholder scan: no TBDs; every step has exact code or commands.

Type consistency: `FeedbackThumb` / `thumb` is `"up" | "down"` in both backend schemas and frontend types. `activity_id`, `athlete_id`, `id` are integers throughout. `next_cursor` is `number | null` on both sides.
