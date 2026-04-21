# Training Plan Import — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the athlete publish a Google Sheet of their weekly plan, pull it into the backend, and teach the debrief pipeline to reason about "planned vs actual" with a compliance score surfaced both in the LLM output and in the UI.

**Architecture:** New `training_plan_entries` table populated by polling a public Google Sheets CSV URL. The existing `_build_athlete_context()` pipeline is extended with `planned_today` + `planned_tomorrow`. System prompt gains a "PLAN VS ACTUAL" section; the `submit_debrief` tool gains a `plan_compliance` field with a strict `NN/100 <sentence>` format. Three UI additions render the signal on Targets, Dashboard, and ActivityDetail.

**Tech Stack:** FastAPI + SQLAlchemy 2 async + Alembic + httpx + pytest (backend), React 18 + TanStack Query v5 + Ant Design + Tailwind (frontend), Anthropic Python SDK for LLM tool calls.

**Spec:** `docs/superpowers/specs/2026-04-21-training-plan-import-design.md`

**Working directory:** Run backend tests from `backend/`; run frontend commands from `frontend/`.

---

## Task 1: Alembic migration 005 — new table + athlete columns

**Files:**
- Create: `backend/migrations/versions/005_training_plan.py`

- [ ] **Step 1: Create the migration file**

```python
"""Training plan entries + athlete sheet URL settings.

Revision ID: 005_training_plan
Revises: 004_activity_desc_hash
Create Date: 2026-04-21

"""
from typing import Sequence, Union

from alembic import op


revision: str = "005_training_plan"
down_revision: Union[str, None] = "004_activity_desc_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


WORKOUT_TYPES = (
    "recovery", "easy", "long", "tempo", "interval",
    "hill", "race", "rest", "cross", "strength",
)


def upgrade() -> None:
    types_list = ", ".join(f"'{t}'" for t in WORKOUT_TYPES)
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS training_plan_entries (
            id SERIAL PRIMARY KEY,
            athlete_id INTEGER NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            workout_type TEXT NOT NULL CHECK (workout_type IN ({types_list})),
            planned_tss REAL,
            planned_duration_min INTEGER,
            planned_distance_km REAL,
            planned_elevation_m INTEGER,
            description TEXT,
            source TEXT NOT NULL DEFAULT 'sheet_csv',
            imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (athlete_id, date)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_training_plan_athlete_date "
        "ON training_plan_entries (athlete_id, date)"
    )
    op.execute(
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS plan_sheet_url TEXT"
    )
    op.execute(
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS plan_synced_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE athletes DROP COLUMN IF EXISTS plan_synced_at")
    op.execute("ALTER TABLE athletes DROP COLUMN IF EXISTS plan_sheet_url")
    op.execute("DROP INDEX IF EXISTS ix_training_plan_athlete_date")
    op.execute("DROP TABLE IF EXISTS training_plan_entries")
```

- [ ] **Step 2: Run migration against dev DB**

Run: `cd backend && alembic upgrade head`
Expected output ends with: `Running upgrade 004_activity_desc_hash -> 005_training_plan`

- [ ] **Step 3: Verify schema**

Run:
```bash
docker compose exec -T postgres psql -U postgres -d stravacoach -c "\d training_plan_entries"
```
Expected: table listed with all 11 columns, the CHECK constraint on `workout_type`, and the `UNIQUE (athlete_id, date)` constraint.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/versions/005_training_plan.py
git commit -m "chore: alembic 005 — training_plan_entries + athlete sheet columns"
```

---

## Task 2: ORM model — `TrainingPlanEntry`

**Files:**
- Create: `backend/app/models/training_plan.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/athlete.py` (add 2 columns + relationship)

- [ ] **Step 1: Write the model file**

`backend/app/models/training_plan.py`:

```python
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.athlete import Athlete


WORKOUT_TYPES = frozenset({
    "recovery", "easy", "long", "tempo", "interval",
    "hill", "race", "rest", "cross", "strength",
})


class TrainingPlanEntry(Base):
    __tablename__ = "training_plan_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    workout_type: Mapped[str] = mapped_column(String(20), nullable=False)
    planned_tss: Mapped[float | None] = mapped_column(Float)
    planned_duration_min: Mapped[int | None] = mapped_column(Integer)
    planned_distance_km: Mapped[float | None] = mapped_column(Float)
    planned_elevation_m: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="sheet_csv", nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    athlete: Mapped["Athlete"] = relationship(back_populates="plan_entries")
```

- [ ] **Step 2: Extend `Athlete`**

In `backend/app/models/athlete.py`, add two columns and the reverse relationship. Add the TYPE_CHECKING import and the new columns before `created_at`:

```python
# add to existing imports near the top of the file:
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Float, ForeignKey, String, Text

# add to TYPE_CHECKING block:
if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.credentials import StravaCredential
    from app.models.metrics import ActivityMetrics, LoadHistory
    from app.models.target import RaceTarget
    from app.models.training_plan import TrainingPlanEntry  # NEW

# inside class Athlete, add BEFORE created_at:
    plan_sheet_url: Mapped[str | None] = mapped_column(Text)
    plan_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

# inside class Athlete relationships block, add:
    plan_entries: Mapped[list["TrainingPlanEntry"]] = relationship(
        back_populates="athlete", cascade="all, delete-orphan"
    )
```

- [ ] **Step 3: Register the model for test-time `create_all`**

In `backend/app/models/__init__.py`, add:

```python
from app.models.training_plan import TrainingPlanEntry  # noqa: F401
```

(Open the file first and confirm it follows the same `noqa: F401` pattern for other models. If not, add both an `import` line and reference the existing style.)

- [ ] **Step 4: Run existing test suite to confirm no regression**

Run: `cd backend && pytest tests/ -x -q`
Expected: 27 passed (or current count), no failures.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/training_plan.py backend/app/models/__init__.py backend/app/models/athlete.py
git commit -m "feat: TrainingPlanEntry model + athlete plan settings columns"
```

---

## Task 3: CSV parser — pure function, TDD

**Files:**
- Create: `backend/app/services/plan_import.py` (parser portion only)
- Create: `backend/tests/test_services/test_plan_import_parser.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_services/test_plan_import_parser.py`:

```python
from datetime import date

import pytest

from app.services.plan_import import ParsedEntry, ParseError, parse_plan_csv


VALID_CSV = """date,workout_type,planned_tss,planned_duration_min,planned_distance_km,planned_elevation_m,description
2026-04-22,long,180,240,35,1200,"4h trail Z2, practice fueling every 30min"
2026-04-23,recovery,40,45,7,50,"flat, HR < LTHR-30"
2026-04-24,rest,,,,,
2026-04-25,interval,95,75,12,150,"20min WU / 6x800m @ 5k pace 2min rest / 15min CD"
"""


def test_valid_csv_parses_all_rows():
    entries, errors = parse_plan_csv(VALID_CSV)
    assert errors == []
    assert len(entries) == 4


def test_blank_numeric_cells_become_none():
    entries, _ = parse_plan_csv(VALID_CSV)
    rest = next(e for e in entries if e.workout_type == "rest")
    assert rest.planned_tss is None
    assert rest.planned_duration_min is None
    assert rest.description is None


def test_dates_parsed_as_date_objects():
    entries, _ = parse_plan_csv(VALID_CSV)
    assert entries[0].date == date(2026, 4, 22)


def test_bad_workout_type_rejects_row_not_file():
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        "2026-04-22,fartlek,60,45,7,,\n"
        "2026-04-23,easy,50,40,6,,\n"
    )
    entries, errors = parse_plan_csv(csv)
    assert len(entries) == 1
    assert entries[0].workout_type == "easy"
    assert len(errors) == 1
    assert errors[0].row_number == 2
    assert "fartlek" in errors[0].reason


def test_bad_date_rejects_row():
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        "next monday,easy,,,,,\n"
    )
    entries, errors = parse_plan_csv(csv)
    assert entries == []
    assert len(errors) == 1
    assert "date" in errors[0].reason.lower()


def test_non_numeric_in_numeric_cell_rejects_row():
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        "2026-04-22,easy,abc,45,7,,\n"
    )
    entries, errors = parse_plan_csv(csv)
    assert entries == []
    assert len(errors) == 1
    assert "planned_tss" in errors[0].reason


def test_missing_header_column_raises():
    csv = "date,workout_type\n2026-04-22,easy\n"
    with pytest.raises(ValueError, match="missing required column"):
        parse_plan_csv(csv)


def test_extra_trailing_columns_ignored():
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description,extra1,extra2\n"
        "2026-04-22,easy,50,40,6,,note,junk1,junk2\n"
    )
    entries, errors = parse_plan_csv(csv)
    assert len(entries) == 1
    assert errors == []


def test_description_truncated_at_1000_chars():
    long_desc = "a" * 1500
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        f"2026-04-22,easy,50,40,6,,\"{long_desc}\"\n"
    )
    entries, _ = parse_plan_csv(csv)
    assert len(entries[0].description) == 1000


def test_workout_type_lowercased():
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        "2026-04-22,LONG,180,240,35,1200,hi\n"
    )
    entries, _ = parse_plan_csv(csv)
    assert entries[0].workout_type == "long"


def test_duplicate_dates_both_kept_in_output():
    # Dedupe happens in the upsert step, not the parser.
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        "2026-04-22,easy,50,,,,\n"
        "2026-04-22,tempo,100,,,,\n"
    )
    entries, errors = parse_plan_csv(csv)
    assert len(entries) == 2
    assert errors == []
```

- [ ] **Step 2: Run tests — all should fail with ImportError**

Run: `cd backend && pytest tests/test_services/test_plan_import_parser.py -v`
Expected: all tests fail because `app.services.plan_import` does not exist yet.

- [ ] **Step 3: Implement the parser**

`backend/app/services/plan_import.py`:

```python
"""Training plan CSV import — pure parser, fetcher, sync orchestrator.

Parser is pure (no I/O). Fetcher + sync functions are added in later tasks.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.models.training_plan import WORKOUT_TYPES


REQUIRED_COLUMNS = (
    "date",
    "workout_type",
    "planned_tss",
    "planned_duration_min",
    "planned_distance_km",
    "planned_elevation_m",
    "description",
)
DESCRIPTION_MAX_LEN = 1000


@dataclass(frozen=True)
class ParsedEntry:
    date: date
    workout_type: str
    planned_tss: float | None
    planned_duration_min: int | None
    planned_distance_km: float | None
    planned_elevation_m: int | None
    description: str | None


@dataclass(frozen=True)
class ParseError:
    row_number: int   # 1-indexed, header is row 1
    reason: str


class RowError(BaseModel):
    row_number: int
    reason: str


class SyncReport(BaseModel):
    status: Literal["ok", "failed"]
    fetched_rows: int = 0
    accepted: int = 0
    rejected: list[RowError] = []
    error: str | None = None


def parse_plan_csv(text: str) -> tuple[list[ParsedEntry], list[ParseError]]:
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return [], []
    _validate_header(header)

    entries: list[ParsedEntry] = []
    errors: list[ParseError] = []
    for idx, row in enumerate(reader, start=2):  # row 1 = header
        try:
            entries.append(_parse_row(row))
        except _RowReject as exc:
            errors.append(ParseError(row_number=idx, reason=exc.reason))
    return entries, errors


def _validate_header(header: list[str]) -> None:
    normalised = [col.strip().lower() for col in header]
    for col in REQUIRED_COLUMNS:
        if col not in normalised:
            raise ValueError(f"missing required column: {col}")


class _RowReject(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason


def _parse_row(row: list[str]) -> ParsedEntry:
    cells = [c.strip() for c in row[: len(REQUIRED_COLUMNS)]]
    while len(cells) < len(REQUIRED_COLUMNS):
        cells.append("")
    date_s, type_s, tss_s, dur_s, dist_s, elev_s, desc_s = cells

    if not date_s:
        raise _RowReject("date is required")
    try:
        parsed_date = date.fromisoformat(date_s)
    except ValueError:
        raise _RowReject(f"date '{date_s}' is not ISO YYYY-MM-DD")

    workout_type = type_s.lower()
    if workout_type not in WORKOUT_TYPES:
        raise _RowReject(
            f"workout_type '{type_s}' not recognised "
            f"(allowed: {', '.join(sorted(WORKOUT_TYPES))})"
        )

    tss = _parse_optional_float(tss_s, "planned_tss")
    duration = _parse_optional_int(dur_s, "planned_duration_min")
    distance = _parse_optional_float(dist_s, "planned_distance_km")
    elevation = _parse_optional_int(elev_s, "planned_elevation_m")

    description = desc_s[:DESCRIPTION_MAX_LEN] if desc_s else None

    return ParsedEntry(
        date=parsed_date,
        workout_type=workout_type,
        planned_tss=tss,
        planned_duration_min=duration,
        planned_distance_km=distance,
        planned_elevation_m=elevation,
        description=description,
    )


def _parse_optional_float(raw: str, field_name: str) -> float | None:
    if raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        raise _RowReject(f"{field_name} '{raw}' is not numeric")


def _parse_optional_int(raw: str, field_name: str) -> int | None:
    if raw == "":
        return None
    try:
        return int(float(raw))  # tolerate "180.0"
    except ValueError:
        raise _RowReject(f"{field_name} '{raw}' is not numeric")
```

- [ ] **Step 4: Run tests — all should pass**

Run: `cd backend && pytest tests/test_services/test_plan_import_parser.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/plan_import.py backend/tests/test_services/test_plan_import_parser.py
git commit -m "feat: plan_import CSV parser with golden-file tests"
```

---

## Task 4: Sheet fetcher — URL validation + httpx GET

**Files:**
- Modify: `backend/app/services/plan_import.py`
- Create: `backend/tests/test_services/test_plan_import_fetch.py`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_services/test_plan_import_fetch.py`:

```python
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.plan_import import (
    InvalidSheetURL,
    SheetFetchError,
    fetch_plan_sheet,
    is_valid_sheet_url,
)


def test_valid_sheet_url_accepted():
    url = "https://docs.google.com/spreadsheets/d/abc123/pub?output=csv"
    assert is_valid_sheet_url(url)


def test_valid_sheet_url_with_gid_accepted():
    url = (
        "https://docs.google.com/spreadsheets/d/abc/pub?"
        "gid=0&single=true&output=csv"
    )
    assert is_valid_sheet_url(url)


def test_non_google_host_rejected():
    assert not is_valid_sheet_url("https://example.com/sheet.csv")


def test_http_instead_of_https_rejected():
    url = "http://docs.google.com/spreadsheets/d/abc/pub?output=csv"
    assert not is_valid_sheet_url(url)


def test_output_not_csv_rejected():
    url = "https://docs.google.com/spreadsheets/d/abc/pub?output=xlsx"
    assert not is_valid_sheet_url(url)


@pytest.mark.asyncio
async def test_fetch_rejects_non_google_url():
    with pytest.raises(InvalidSheetURL):
        await fetch_plan_sheet("https://evil.example.com/sheet.csv")


@pytest.mark.asyncio
async def test_fetch_returns_text_on_200():
    csv_body = "date,workout_type\n2026-04-22,easy\n"
    mock_response = httpx.Response(200, text=csv_body)

    async def handler(_request: httpx.Request) -> httpx.Response:
        return mock_response

    transport = httpx.MockTransport(handler)
    url = "https://docs.google.com/spreadsheets/d/abc/pub?output=csv"
    result = await fetch_plan_sheet(url, transport=transport)
    assert result == csv_body


@pytest.mark.asyncio
async def test_fetch_raises_on_non_200():
    mock_response = httpx.Response(403, text="forbidden")

    async def handler(_request: httpx.Request) -> httpx.Response:
        return mock_response

    transport = httpx.MockTransport(handler)
    url = "https://docs.google.com/spreadsheets/d/abc/pub?output=csv"
    with pytest.raises(SheetFetchError, match="403"):
        await fetch_plan_sheet(url, transport=transport)


@pytest.mark.asyncio
async def test_fetch_raises_on_timeout():
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    transport = httpx.MockTransport(handler)
    url = "https://docs.google.com/spreadsheets/d/abc/pub?output=csv"
    with pytest.raises(SheetFetchError, match="timeout"):
        await fetch_plan_sheet(url, transport=transport)
```

- [ ] **Step 2: Run tests — fail with ImportError**

Run: `cd backend && pytest tests/test_services/test_plan_import_fetch.py -v`
Expected: ImportError on `fetch_plan_sheet`, `is_valid_sheet_url`, etc.

- [ ] **Step 3: Append fetcher to `plan_import.py`**

Append to `backend/app/services/plan_import.py`:

```python
import re
import httpx


SHEET_URL_REGEX = re.compile(
    r"^https://docs\.google\.com/spreadsheets/.+/pub\?.*output=csv.*$"
)
FETCH_TIMEOUT_SEC = 10.0


class InvalidSheetURL(ValueError):
    """Raised when the provided sheet URL is not a Google Sheets published CSV link."""


class SheetFetchError(RuntimeError):
    """Raised when the fetch attempt fails (non-200, timeout, network error)."""


def is_valid_sheet_url(url: str) -> bool:
    return bool(SHEET_URL_REGEX.match(url))


async def fetch_plan_sheet(
    url: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> str:
    if not is_valid_sheet_url(url):
        raise InvalidSheetURL(
            "URL must be a Google Sheets published CSV link "
            "(https://docs.google.com/spreadsheets/.../pub?output=csv)"
        )
    try:
        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT_SEC, transport=transport, follow_redirects=True
        ) as client:
            response = await client.get(url)
    except httpx.TimeoutException as exc:
        raise SheetFetchError(f"sheet fetch timeout: {exc}") from exc
    except httpx.HTTPError as exc:
        raise SheetFetchError(f"sheet fetch failed: {exc}") from exc
    if response.status_code != 200:
        raise SheetFetchError(
            f"sheet fetch returned {response.status_code}: {response.text[:200]}"
        )
    return response.text
```

- [ ] **Step 4: Run tests — all should pass**

Run: `cd backend && pytest tests/test_services/test_plan_import_fetch.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/plan_import.py backend/tests/test_services/test_plan_import_fetch.py
git commit -m "feat: plan_import fetcher with URL validation + timeout"
```

---

## Task 5: `sync_plan` upsert orchestrator

**Files:**
- Modify: `backend/app/services/plan_import.py`
- Create: `backend/tests/test_services/test_plan_import_sync.py`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_services/test_plan_import_sync.py`:

```python
from datetime import date, datetime, timezone
from typing import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.training_plan import TrainingPlanEntry
from app.services.plan_import import sync_plan


@pytest.fixture
async def athlete_with_sheet(db_session: AsyncSession) -> Athlete:
    athlete = Athlete(
        strava_athlete_id=99,
        plan_sheet_url="https://docs.google.com/spreadsheets/d/abc/pub?output=csv",
    )
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)
    return athlete


CSV_BODY_V1 = """date,workout_type,planned_tss,planned_duration_min,planned_distance_km,planned_elevation_m,description
2026-04-22,long,180,240,35,1200,"long run v1"
2026-04-23,recovery,40,45,7,50,"easy"
"""

CSV_BODY_V2 = """date,workout_type,planned_tss,planned_duration_min,planned_distance_km,planned_elevation_m,description
2026-04-22,long,200,260,36,1300,"long run v2 — bumped volume"
2026-04-23,recovery,40,45,7,50,"easy"
2026-04-24,rest,,,,,
"""


@pytest.mark.asyncio
async def test_sync_plan_inserts_entries(
    db_session: AsyncSession, athlete_with_sheet: Athlete, monkeypatch
):
    async def fake_fetch(_url: str) -> str:
        return CSV_BODY_V1

    monkeypatch.setattr(
        "app.services.plan_import.fetch_plan_sheet", fake_fetch
    )

    report = await sync_plan(athlete_with_sheet.id, db_session)

    assert report.status == "ok"
    assert report.accepted == 2
    assert report.rejected == []

    rows = (
        await db_session.execute(
            select(TrainingPlanEntry).where(
                TrainingPlanEntry.athlete_id == athlete_with_sheet.id
            )
        )
    ).scalars().all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_sync_plan_upserts_later_wins(
    db_session: AsyncSession, athlete_with_sheet: Athlete, monkeypatch
):
    async def fake_fetch_v1(_url: str) -> str:
        return CSV_BODY_V1

    monkeypatch.setattr("app.services.plan_import.fetch_plan_sheet", fake_fetch_v1)
    await sync_plan(athlete_with_sheet.id, db_session)

    async def fake_fetch_v2(_url: str) -> str:
        return CSV_BODY_V2

    monkeypatch.setattr("app.services.plan_import.fetch_plan_sheet", fake_fetch_v2)
    report = await sync_plan(athlete_with_sheet.id, db_session)

    assert report.status == "ok"
    assert report.accepted == 3

    rows = (
        await db_session.execute(
            select(TrainingPlanEntry).where(
                TrainingPlanEntry.athlete_id == athlete_with_sheet.id
            )
        )
    ).scalars().all()
    assert len(rows) == 3  # 2 updated + 1 new, NOT 5
    long_row = next(r for r in rows if r.date == date(2026, 4, 22))
    assert long_row.planned_tss == 200  # updated value wins
    assert "v2" in (long_row.description or "")


@pytest.mark.asyncio
async def test_sync_plan_updates_plan_synced_at(
    db_session: AsyncSession, athlete_with_sheet: Athlete, monkeypatch
):
    async def fake_fetch(_url: str) -> str:
        return CSV_BODY_V1

    monkeypatch.setattr("app.services.plan_import.fetch_plan_sheet", fake_fetch)

    before = datetime.now(timezone.utc)
    await sync_plan(athlete_with_sheet.id, db_session)
    await db_session.refresh(athlete_with_sheet)
    assert athlete_with_sheet.plan_synced_at is not None
    assert athlete_with_sheet.plan_synced_at >= before


@pytest.mark.asyncio
async def test_sync_plan_no_url_configured(db_session: AsyncSession):
    athlete = Athlete(strava_athlete_id=100)
    db_session.add(athlete)
    await db_session.commit()

    report = await sync_plan(athlete.id, db_session)
    assert report.status == "failed"
    assert "not configured" in (report.error or "").lower()


@pytest.mark.asyncio
async def test_sync_plan_fetch_failure_does_not_mutate_db(
    db_session: AsyncSession, athlete_with_sheet: Athlete, monkeypatch
):
    from app.services.plan_import import SheetFetchError

    async def fake_fetch(_url: str) -> str:
        raise SheetFetchError("boom")

    monkeypatch.setattr("app.services.plan_import.fetch_plan_sheet", fake_fetch)

    report = await sync_plan(athlete_with_sheet.id, db_session)
    assert report.status == "failed"
    assert "boom" in (report.error or "")

    rows = (
        await db_session.execute(
            select(TrainingPlanEntry).where(
                TrainingPlanEntry.athlete_id == athlete_with_sheet.id
            )
        )
    ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_sync_plan_rejected_rows_in_report(
    db_session: AsyncSession, athlete_with_sheet: Athlete, monkeypatch
):
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        "2026-04-22,fartlek,60,45,7,,\n"
        "2026-04-23,easy,50,40,6,,\n"
    )

    async def fake_fetch(_url: str) -> str:
        return csv

    monkeypatch.setattr("app.services.plan_import.fetch_plan_sheet", fake_fetch)
    report = await sync_plan(athlete_with_sheet.id, db_session)
    assert report.status == "ok"
    assert report.accepted == 1
    assert len(report.rejected) == 1
    assert report.rejected[0].row_number == 2
```

- [ ] **Step 2: Run tests — all fail with ImportError or NameError**

Run: `cd backend && pytest tests/test_services/test_plan_import_sync.py -v`

- [ ] **Step 3: Implement sync_plan**

Append to `backend/app/services/plan_import.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.training_plan import TrainingPlanEntry


async def sync_plan(athlete_id: int, db: AsyncSession) -> SyncReport:
    athlete = await db.get(Athlete, athlete_id)
    if athlete is None:
        return SyncReport(status="failed", error="athlete not found")
    if not athlete.plan_sheet_url:
        return SyncReport(status="failed", error="plan sheet URL not configured")

    try:
        csv_text = await fetch_plan_sheet(athlete.plan_sheet_url)
    except (InvalidSheetURL, SheetFetchError) as exc:
        return SyncReport(status="failed", error=str(exc))

    try:
        parsed, errors = parse_plan_csv(csv_text)
    except ValueError as exc:
        return SyncReport(status="failed", error=f"CSV parse error: {exc}")

    await _upsert_entries(db, athlete_id, parsed)
    athlete.plan_synced_at = datetime.now(timezone.utc)
    await db.commit()

    return SyncReport(
        status="ok",
        fetched_rows=len(parsed) + len(errors),
        accepted=len(parsed),
        rejected=[RowError(row_number=e.row_number, reason=e.reason) for e in errors],
    )


async def _upsert_entries(
    db: AsyncSession, athlete_id: int, entries: list[ParsedEntry]
) -> None:
    """Delete-then-insert by (athlete_id, date). Simple, portable across
    Postgres + SQLite test engine. Dedup by date within the batch —
    last one wins."""
    if not entries:
        return
    latest_by_date: dict[date, ParsedEntry] = {}
    for entry in entries:
        latest_by_date[entry.date] = entry

    dates = list(latest_by_date.keys())
    await db.execute(
        delete(TrainingPlanEntry).where(
            TrainingPlanEntry.athlete_id == athlete_id,
            TrainingPlanEntry.date.in_(dates),
        )
    )
    await db.flush()
    for entry in latest_by_date.values():
        db.add(
            TrainingPlanEntry(
                athlete_id=athlete_id,
                date=entry.date,
                workout_type=entry.workout_type,
                planned_tss=entry.planned_tss,
                planned_duration_min=entry.planned_duration_min,
                planned_distance_km=entry.planned_distance_km,
                planned_elevation_m=entry.planned_elevation_m,
                description=entry.description,
                source="sheet_csv",
            )
        )
```

- [ ] **Step 4: Run tests — all pass**

Run: `cd backend && pytest tests/test_services/test_plan_import_sync.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/plan_import.py backend/tests/test_services/test_plan_import_sync.py
git commit -m "feat: plan_import sync_plan orchestrator (fetch + parse + upsert)"
```

---

## Task 6: `get_planned_for_date` lookup helper

**Files:**
- Modify: `backend/app/services/plan_import.py`
- Create: `backend/tests/test_services/test_plan_import_lookup.py`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_services/test_plan_import_lookup.py`:

```python
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.training_plan import TrainingPlanEntry
from app.services.plan_import import get_planned_for_date


@pytest.fixture
async def athlete(db_session: AsyncSession) -> Athlete:
    athlete = Athlete(strava_athlete_id=1)
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)
    return athlete


@pytest.mark.asyncio
async def test_returns_none_when_no_entry(db_session: AsyncSession, athlete: Athlete):
    result = await get_planned_for_date(athlete.id, date(2026, 4, 22), db_session)
    assert result is None


@pytest.mark.asyncio
async def test_returns_planned_context_when_entry_exists(
    db_session: AsyncSession, athlete: Athlete
):
    db_session.add(
        TrainingPlanEntry(
            athlete_id=athlete.id,
            date=date(2026, 4, 22),
            workout_type="long",
            planned_tss=180,
            planned_duration_min=240,
            planned_distance_km=35,
            planned_elevation_m=1200,
            description="4h trail",
        )
    )
    await db_session.commit()

    result = await get_planned_for_date(athlete.id, date(2026, 4, 22), db_session)
    assert result is not None
    assert result.workout_type == "long"
    assert result.planned_tss == 180
    assert result.description == "4h trail"


@pytest.mark.asyncio
async def test_returns_none_for_other_athletes_entry(
    db_session: AsyncSession, athlete: Athlete
):
    other = Athlete(strava_athlete_id=2)
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    db_session.add(
        TrainingPlanEntry(
            athlete_id=other.id,
            date=date(2026, 4, 22),
            workout_type="easy",
        )
    )
    await db_session.commit()

    result = await get_planned_for_date(athlete.id, date(2026, 4, 22), db_session)
    assert result is None
```

- [ ] **Step 2: Run tests — fail with ImportError**

Run: `cd backend && pytest tests/test_services/test_plan_import_lookup.py -v`

- [ ] **Step 3: Implement the lookup with lazy import**

The return type lives in `app.agents.schema` and is added in Task 7. Use a lazy import inside the function so `plan_import.py` stays importable right now (Tasks 3–5 tests must still run after this commit).

Append to `backend/app/services/plan_import.py`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.schema import PlannedWorkoutContext


async def get_planned_for_date(
    athlete_id: int, day: date, db: AsyncSession
) -> "PlannedWorkoutContext | None":
    # Lazy import: PlannedWorkoutContext is added to schema.py in Task 7.
    # Keeping it lazy means plan_import.py is safe to import before Task 7 lands.
    from app.agents.schema import PlannedWorkoutContext

    result = await db.execute(
        select(TrainingPlanEntry).where(
            TrainingPlanEntry.athlete_id == athlete_id,
            TrainingPlanEntry.date == day,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        return None
    return PlannedWorkoutContext(
        date=entry.date,
        workout_type=entry.workout_type,
        planned_tss=entry.planned_tss,
        planned_duration_min=entry.planned_duration_min,
        planned_distance_km=entry.planned_distance_km,
        planned_elevation_m=entry.planned_elevation_m,
        description=entry.description,
    )
```

Because the import is lazy, the module remains importable. Task 6's own unit tests exercise the function — they WILL call `get_planned_for_date`, which triggers the lazy import, which fails until Task 7 lands. That's why Step 4 defers running this task's tests.

- [ ] **Step 4: Confirm plan_import.py is still importable, then defer test run to Task 7**

Run a quick sanity check that the module imports cleanly (the lazy import keeps it valid):

Run: `cd backend && python -c "from app.services.plan_import import get_planned_for_date; print('ok')"`
Expected: `ok`.

Also run Tasks 3–5 tests to confirm nothing regressed:

Run: `cd backend && pytest tests/test_services/test_plan_import_parser.py tests/test_services/test_plan_import_fetch.py tests/test_services/test_plan_import_sync.py -v`
Expected: all green (same counts as before).

Do NOT run this task's own tests yet — they need `PlannedWorkoutContext`, which arrives in Task 7.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/plan_import.py backend/tests/test_services/test_plan_import_lookup.py
git commit -m "feat: get_planned_for_date lookup helper (tests deferred to Task 7)"
```

---

## Task 7: Extend `AthleteContext` with planned workouts

**Files:**
- Modify: `backend/app/agents/schema.py`
- Create: `backend/tests/test_agents/test_schema_planned.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_agents/test_schema_planned.py`:

```python
from datetime import date

from app.agents.schema import AthleteContext, PlannedWorkoutContext


def test_planned_workout_context_requires_date_and_type():
    planned = PlannedWorkoutContext(date=date(2026, 4, 22), workout_type="long")
    assert planned.date == date(2026, 4, 22)
    assert planned.workout_type == "long"
    assert planned.planned_tss is None


def test_athlete_context_defaults_planned_to_none():
    context = AthleteContext(
        lthr=155,
        threshold_pace_sec_km=300,
        tss_30d_avg=50,
        acwr=1.0,
        ctl=60,
        atl=55,
        tsb=5,
        training_phase="Build",
    )
    assert context.planned_today is None
    assert context.planned_tomorrow is None


def test_athlete_context_accepts_planned_workouts():
    planned = PlannedWorkoutContext(date=date(2026, 4, 22), workout_type="long")
    context = AthleteContext(
        lthr=155,
        threshold_pace_sec_km=300,
        tss_30d_avg=50,
        acwr=1.0,
        ctl=60,
        atl=55,
        tsb=5,
        training_phase="Build",
        planned_today=planned,
    )
    assert context.planned_today is not None
    assert context.planned_today.workout_type == "long"
```

- [ ] **Step 2: Run test — fails on ImportError for `PlannedWorkoutContext`**

Run: `cd backend && pytest tests/test_agents/test_schema_planned.py -v`

- [ ] **Step 3: Extend `schema.py`**

Replace contents of `backend/app/agents/schema.py`:

```python
from datetime import date

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
    elevation_gain_m: float = 0.0
    cadence_avg: float | None = None


class RaceTargetContext(BaseModel):
    race_name: str
    weeks_out: int
    distance_km: float
    goal_time_sec: int | None = None
    training_phase: str  # Base / Build / Peak / Taper


class PlannedWorkoutContext(BaseModel):
    date: date
    workout_type: str
    planned_tss: float | None = None
    planned_duration_min: int | None = None
    planned_distance_km: float | None = None
    planned_elevation_m: int | None = None
    description: str | None = None


class AthleteContext(BaseModel):
    lthr: int
    threshold_pace_sec_km: int
    tss_30d_avg: float
    acwr: float
    ctl: float
    atl: float
    tsb: float
    training_phase: str
    race_target: RaceTargetContext | None = None
    planned_today: PlannedWorkoutContext | None = None
    planned_tomorrow: PlannedWorkoutContext | None = None


class DebriefOutput(BaseModel):
    load_verdict: str = Field(max_length=500)
    technical_insight: str = Field(max_length=500)
    next_session_action: str = Field(max_length=500)
    nutrition_protocol: str = Field(default="", max_length=500)
    vmm_projection: str = Field(default="", max_length=500)
    plan_compliance: str = Field(default="", max_length=300)
```

- [ ] **Step 4: Run schema tests + Task 6's deferred tests**

Run: `cd backend && pytest tests/test_agents/test_schema_planned.py tests/test_services/test_plan_import_lookup.py -v`
Expected: all pass (3 schema + 3 lookup = 6 passed).

- [ ] **Step 5: Run the whole suite to catch collateral damage**

Run: `cd backend && pytest tests/ -x -q`
Expected: all previous passes still pass, plus the new tests.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/schema.py backend/tests/test_agents/test_schema_planned.py
git commit -m "feat: PlannedWorkoutContext + AthleteContext.planned_today/tomorrow"
```

---

## Task 8: `/plan` router — 4 endpoints

**Files:**
- Create: `backend/app/routers/plan.py`
- Create: `backend/tests/test_routers/test_plan.py`
- Modify: `backend/app/main.py` (register the router)

- [ ] **Step 1: Write failing endpoint tests**

`backend/tests/test_routers/test_plan.py`:

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.training_plan import TrainingPlanEntry


VALID_URL = "https://docs.google.com/spreadsheets/d/abc/pub?output=csv"


async def _make_athlete(db: AsyncSession, strava_id: int = 1) -> Athlete:
    athlete = Athlete(strava_athlete_id=strava_id)
    db.add(athlete)
    await db.commit()
    await db.refresh(athlete)
    return athlete


def test_put_plan_config_saves_url(client: TestClient, db_session: AsyncSession):
    import asyncio

    athlete = asyncio.run(_make_athlete(db_session))
    response = client.put(
        "/plan/config",
        json={"athlete_id": athlete.id, "sheet_url": VALID_URL},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sheet_url"] == VALID_URL
    assert body["athlete_id"] == athlete.id


def test_put_plan_config_rejects_bad_url(
    client: TestClient, db_session: AsyncSession
):
    import asyncio

    athlete = asyncio.run(_make_athlete(db_session))
    response = client.put(
        "/plan/config",
        json={"athlete_id": athlete.id, "sheet_url": "https://evil.example.com/x.csv"},
    )
    assert response.status_code == 400
    assert "google sheets" in response.text.lower()


def test_delete_plan_config_clears_url(
    client: TestClient, db_session: AsyncSession
):
    import asyncio

    athlete = asyncio.run(_make_athlete(db_session))
    client.put(
        "/plan/config",
        json={"athlete_id": athlete.id, "sheet_url": VALID_URL},
    )
    response = client.delete(f"/plan/config?athlete_id={athlete.id}")
    assert response.status_code == 204

    asyncio.run(db_session.refresh(athlete))
    assert athlete.plan_sheet_url is None


def test_get_plan_range_returns_entries(
    client: TestClient, db_session: AsyncSession
):
    import asyncio

    athlete = asyncio.run(_make_athlete(db_session))
    db_session.add_all(
        [
            TrainingPlanEntry(
                athlete_id=athlete.id,
                date=date(2026, 4, 22),
                workout_type="long",
                planned_tss=180,
            ),
            TrainingPlanEntry(
                athlete_id=athlete.id,
                date=date(2026, 4, 23),
                workout_type="recovery",
                planned_tss=40,
            ),
            TrainingPlanEntry(
                athlete_id=athlete.id,
                date=date(2026, 5, 10),
                workout_type="race",
            ),
        ]
    )
    asyncio.run(db_session.commit())

    response = client.get(
        f"/plan?athlete_id={athlete.id}&from_=2026-04-22&to=2026-04-30"
    )
    assert response.status_code == 200, response.text
    entries = response.json()
    assert len(entries) == 2
    assert entries[0]["workout_type"] == "long"
    assert entries[1]["workout_type"] == "recovery"


def test_post_sync_delegates_to_service(
    client: TestClient, db_session: AsyncSession, monkeypatch
):
    import asyncio
    from app.services import plan_import

    athlete = asyncio.run(_make_athlete(db_session))

    async def fake_sync(athlete_id: int, _db):
        assert athlete_id == athlete.id
        return plan_import.SyncReport(
            status="ok", fetched_rows=2, accepted=2, rejected=[]
        )

    monkeypatch.setattr("app.routers.plan.sync_plan", fake_sync)
    response = client.post("/plan/sync", json={"athlete_id": athlete.id})
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "fetched_rows": 2,
        "accepted": 2,
        "rejected": [],
        "error": None,
    }
```

- [ ] **Step 2: Run tests — fail (router not registered)**

Run: `cd backend && pytest tests/test_routers/test_plan.py -v`

- [ ] **Step 3: Implement the router**

`backend/app/routers/plan.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.athlete import Athlete
from app.models.training_plan import TrainingPlanEntry
from app.services.plan_import import (
    SyncReport,
    is_valid_sheet_url,
    sync_plan,
)

router = APIRouter(prefix="/plan", tags=["plan"])


class PlanConfigIn(BaseModel):
    athlete_id: int = Field(gt=0)
    sheet_url: str = Field(min_length=1, max_length=500)


class PlanConfigOut(BaseModel):
    athlete_id: int
    sheet_url: str | None
    plan_synced_at: str | None


class PlanSyncIn(BaseModel):
    athlete_id: int = Field(gt=0)


class PlanEntryOut(BaseModel):
    date: date
    workout_type: str
    planned_tss: float | None
    planned_duration_min: int | None
    planned_distance_km: float | None
    planned_elevation_m: int | None
    description: str | None


@router.put("/config", response_model=PlanConfigOut)
async def put_plan_config(
    data: PlanConfigIn, db: AsyncSession = Depends(get_db)
) -> PlanConfigOut:
    if not is_valid_sheet_url(data.sheet_url):
        raise HTTPException(
            status_code=400,
            detail="URL must be a Google Sheets published CSV link "
            "(https://docs.google.com/spreadsheets/.../pub?output=csv)",
        )
    athlete = await db.get(Athlete, data.athlete_id)
    if athlete is None:
        raise HTTPException(status_code=404, detail="athlete not found")
    athlete.plan_sheet_url = data.sheet_url
    await db.commit()
    await db.refresh(athlete)
    return PlanConfigOut(
        athlete_id=athlete.id,
        sheet_url=athlete.plan_sheet_url,
        plan_synced_at=athlete.plan_synced_at.isoformat()
        if athlete.plan_synced_at
        else None,
    )


@router.delete("/config", status_code=204)
async def delete_plan_config(
    athlete_id: int, db: AsyncSession = Depends(get_db)
) -> Response:
    athlete = await db.get(Athlete, athlete_id)
    if athlete is None:
        raise HTTPException(status_code=404, detail="athlete not found")
    athlete.plan_sheet_url = None
    athlete.plan_synced_at = None
    await db.commit()
    return Response(status_code=204)


@router.post("/sync", response_model=SyncReport)
async def post_plan_sync(
    data: PlanSyncIn, db: AsyncSession = Depends(get_db)
) -> SyncReport:
    return await sync_plan(data.athlete_id, db)


@router.get("", response_model=list[PlanEntryOut])
async def get_plan_range(
    athlete_id: int,
    from_: date = Query(..., alias="from_"),
    to: date = Query(...),
    db: AsyncSession = Depends(get_db),
) -> list[PlanEntryOut]:
    result = await db.execute(
        select(TrainingPlanEntry)
        .where(
            TrainingPlanEntry.athlete_id == athlete_id,
            TrainingPlanEntry.date >= from_,
            TrainingPlanEntry.date <= to,
        )
        .order_by(TrainingPlanEntry.date)
    )
    rows = result.scalars().all()
    return [
        PlanEntryOut(
            date=row.date,
            workout_type=row.workout_type,
            planned_tss=row.planned_tss,
            planned_duration_min=row.planned_duration_min,
            planned_distance_km=row.planned_distance_km,
            planned_elevation_m=row.planned_elevation_m,
            description=row.description,
        )
        for row in rows
    ]
```

- [ ] **Step 4: Register the router in `backend/app/main.py`**

Add `plan` to the imports and `register_routes`:

```python
# Change the import line to include plan:
from app.routers import (
    activities, athletes, auth, dashboard, feedback, onboarding,
    plan, targets, webhook,
)

# Inside register_routes, after the existing include_router calls, add:
    api.include_router(plan.router)
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_routers/test_plan.py -v`
Expected: 5 passed.

- [ ] **Step 6: Run the whole suite**

Run: `cd backend && pytest tests/ -x -q`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/plan.py backend/tests/test_routers/test_plan.py backend/app/main.py
git commit -m "feat: /plan router with 4 endpoints (PUT/DELETE config, POST sync, GET range)"
```

---

## Task 9: Populate `planned_today` / `planned_tomorrow` in `_build_athlete_context`

**Files:**
- Modify: `backend/app/services/activity_ingestion.py`
- Create: `backend/tests/test_services/test_activity_ingestion_plan_context.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_services/test_activity_ingestion_plan_context.py`:

```python
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.athlete import Athlete, AthleteProfile
from app.models.training_plan import TrainingPlanEntry
from app.services.activity_ingestion import _build_athlete_context


@pytest.mark.asyncio
async def test_build_context_includes_planned_today_and_tomorrow(
    db_session: AsyncSession,
):
    athlete = Athlete(strava_athlete_id=1)
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)

    activity_date = date(2026, 4, 22)
    db_session.add_all(
        [
            TrainingPlanEntry(
                athlete_id=athlete.id,
                date=activity_date,
                workout_type="long",
                planned_tss=180,
            ),
            TrainingPlanEntry(
                athlete_id=athlete.id,
                date=date(2026, 4, 23),
                workout_type="recovery",
                planned_tss=40,
            ),
        ]
    )
    await db_session.commit()

    context = await _build_athlete_context(
        db_session, athlete.id, profile=None, activity_date=activity_date
    )

    assert context.planned_today is not None
    assert context.planned_today.workout_type == "long"
    assert context.planned_tomorrow is not None
    assert context.planned_tomorrow.workout_type == "recovery"


@pytest.mark.asyncio
async def test_build_context_planned_none_when_no_entries(
    db_session: AsyncSession,
):
    athlete = Athlete(strava_athlete_id=1)
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)

    context = await _build_athlete_context(
        db_session, athlete.id, profile=None, activity_date=date(2026, 4, 22)
    )
    assert context.planned_today is None
    assert context.planned_tomorrow is None
```

- [ ] **Step 2: Run test — fails because `_build_athlete_context` doesn't take `activity_date`**

Run: `cd backend && pytest tests/test_services/test_activity_ingestion_plan_context.py -v`

- [ ] **Step 3: Update `_build_athlete_context` signature + populate planned fields**

In `backend/app/services/activity_ingestion.py`:

First add the import near other service imports:

```python
from app.services.plan_import import get_planned_for_date
```

Then update the function signature and body. Find the existing `_build_athlete_context` and replace with:

```python
from datetime import date as _date, timedelta

async def _build_athlete_context(
    session: AsyncSession,
    athlete_id: int,
    profile: AthleteProfile | None,
    activity_date: _date | None = None,
) -> AthleteContext:
    load = await _latest_load(session, athlete_id)
    tss_avg = await _tss_30d_avg(session, athlete_id)
    target = await _find_nearest_target(session, athlete_id)

    planned_today = None
    planned_tomorrow = None
    if activity_date is not None:
        planned_today = await get_planned_for_date(
            athlete_id, activity_date, session
        )
        planned_tomorrow = await get_planned_for_date(
            athlete_id, activity_date + timedelta(days=1), session
        )

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
        planned_today=planned_today,
        planned_tomorrow=planned_tomorrow,
    )
```

- [ ] **Step 4: Update the caller to pass `activity_date`**

Find the call site in `process_activity_metrics` (around line 148). Before:

```python
context = await _build_athlete_context(session, activity.athlete_id, profile)
```

After:

```python
activity_date = activity.start_date.date() if activity.start_date else None
context = await _build_athlete_context(
    session, activity.athlete_id, profile, activity_date=activity_date
)
```

- [ ] **Step 5: Run new tests + full suite**

Run: `cd backend && pytest tests/test_services/test_activity_ingestion_plan_context.py -v`
Expected: 2 passed.

Run: `cd backend && pytest tests/ -x -q`
Expected: all green (existing activity-ingestion tests still pass because `activity_date` defaults to `None`).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/activity_ingestion.py backend/tests/test_services/test_activity_ingestion_plan_context.py
git commit -m "feat: populate planned_today/planned_tomorrow in AthleteContext"
```

---

## Task 10: Prompt additions — SYSTEM_PROMPT + conditional prompt block

**Files:**
- Modify: `backend/app/agents/prompts.py`
- Create: `backend/tests/test_agents/test_prompts_planned.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_agents/test_prompts_planned.py`:

```python
from app.agents.prompts import SYSTEM_PROMPT, build_debrief_prompt


BASE_ACTIVITY = {
    "activity_name": "morning",
    "duration_sec": 3600,
    "distance_m": 12000,
    "sport_type": "Run",
    "tss": 80,
    "hr_tss": 80,
    "hr_drift_pct": 3.2,
    "aerobic_decoupling_pct": 2.1,
    "ngp_sec_km": 330,
    "zone_distribution": {"z1_pct": 10, "z2_pct": 60, "z3_pct": 20, "z4_pct": 8, "z5_pct": 2},
    "elevation_gain_m": 200,
    "cadence_avg": 175,
}


BASE_CONTEXT = {
    "lthr": 165,
    "threshold_pace_sec_km": 300,
    "tss_30d_avg": 70,
    "acwr": 1.1,
    "ctl": 55,
    "atl": 60,
    "tsb": -5,
    "training_phase": "Build",
    "race_target": None,
    "planned_today": None,
    "planned_tomorrow": None,
}


def test_system_prompt_contains_plan_vs_actual_section():
    assert "PLAN VS ACTUAL" in SYSTEM_PROMPT
    assert "TYPE BREAK" in SYSTEM_PROMPT
    assert "plan_compliance" in SYSTEM_PROMPT or "NN/100" in SYSTEM_PROMPT


def test_build_prompt_omits_plan_section_when_no_plan():
    prompt = build_debrief_prompt(BASE_ACTIVITY, BASE_CONTEXT)
    assert "PLANNED WORKOUT" not in prompt
    assert "PLANNED TOMORROW" not in prompt


def test_build_prompt_includes_plan_section_when_planned_today_present():
    context = {
        **BASE_CONTEXT,
        "planned_today": {
            "date": "2026-04-22",
            "workout_type": "long",
            "planned_tss": 180,
            "planned_duration_min": 240,
            "planned_distance_km": 35,
            "planned_elevation_m": 1200,
            "description": "4h trail Z2",
        },
    }
    prompt = build_debrief_prompt(BASE_ACTIVITY, context)
    assert "PLANNED WORKOUT (today)" in prompt
    assert "Type: long" in prompt
    assert "Planned TSS: 180" in prompt
    assert "4h trail Z2" in prompt


def test_build_prompt_includes_tomorrow_when_present():
    context = {
        **BASE_CONTEXT,
        "planned_tomorrow": {
            "date": "2026-04-23",
            "workout_type": "recovery",
            "planned_tss": 40,
            "planned_duration_min": 45,
            "planned_distance_km": None,
            "planned_elevation_m": None,
            "description": None,
        },
    }
    prompt = build_debrief_prompt(BASE_ACTIVITY, context)
    assert "PLANNED TOMORROW" in prompt
    assert "recovery" in prompt
    assert "45 min" in prompt
```

- [ ] **Step 2: Run tests — fail**

Run: `cd backend && pytest tests/test_agents/test_prompts_planned.py -v`

- [ ] **Step 3: Patch `SYSTEM_PROMPT`**

In `backend/app/agents/prompts.py`, insert a new block between the existing `CADENCE FLAG:` section and the `CLIMBING/DESCENDING VMM FLAGS:` section. Find the line ending `Below 170 spm: ...` and the following line for cadence drop; insert this block AFTER the cadence drop line and BEFORE `CLIMBING/DESCENDING VMM FLAGS:`:

```
=== PLAN VS ACTUAL (only when [PLANNED_WORKOUT (today)] is provided) ===
Compute compliance on 3 axes:
- TSS delta:      actual_tss / planned_tss × 100     (report as %)
- Duration delta: actual_min / planned_min × 100
- Type fidelity:  did execution match planned workout_type?

Fidelity rules:
- planned recovery|easy, but Z3+Z4+Z5 > 20%                    → TYPE BREAK (ran hard on recovery day)
- planned tempo|interval|hill, but Z3+Z4+Z5 < 15%              → TYPE BREAK (skipped the quality)
- planned long, but duration < 75% of planned_duration_min     → TYPE BREAK (cut short)

Flag rules:
- actual_tss > planned_tss × 1.20 AND planned_type in {recovery, easy}
      → "Overcooked an easy day — tomorrow's quality session is now at risk."
- actual_tss < planned_tss × 0.80 AND duration > 10 min
      → "Plan underdelivered — diagnose why (HR drift, RPE, life stress, weather)."
- TYPE BREAK detected
      → Name the specific mismatch with numbers, then override next_session_action
        regardless of what [PLANNED TOMORROW] says.

Use [PLANNED TOMORROW] to shape next_session_action. If today broke the plan hard
(two or more axes failed), tomorrow must be recovery, not the planned session.

=== plan_compliance OUTPUT FORMAT ===
When a plan exists for today, emit plan_compliance as a single string starting
with a 1-3 digit integer 0-100, then "/100 ", then one sentence. Example:
  "62/100 Overcooked an easy day — tomorrow's quality session is now at risk."
If no plan exists (no [PLANNED WORKOUT (today)] block), emit empty string.
```

Also update the final "=== OUTPUT RULES ===" list to mention the 6th field:

```
6. plan_compliance: Only when [PLANNED WORKOUT (today)] is supplied. Format: "NN/100 <one sentence>".
```

- [ ] **Step 4: Patch `build_debrief_prompt()`**

Replace the `build_debrief_prompt` function body. The returned list of lines must conditionally append planned blocks. Replace the whole function:

```python
def build_debrief_prompt(activity: dict, context: dict) -> str:
    dur_min = activity["duration_sec"] // 60
    dist_km = activity["distance_m"] / 1000
    elev = activity.get("elevation_gain_m", 0)
    cadence = activity.get("cadence_avg")
    cadence_str = f"{cadence:.0f} spm" if cadence else "no data"

    z = activity.get("zone_distribution", {})
    zones_str = (
        f"Z1={z.get('z1_pct', 0):.1f}% Z2={z.get('z2_pct', 0):.1f}% "
        f"Z3={z.get('z3_pct', 0):.1f}% Z4={z.get('z4_pct', 0):.1f}% Z5={z.get('z5_pct', 0):.1f}%"
    )

    threshold_pace_min = context["threshold_pace_sec_km"] / 60
    ngp_min = activity["ngp_sec_km"] / 60 if activity["ngp_sec_km"] else 0

    target = context.get("race_target")
    race_str = (
        f"{target['race_name']} | {target['distance_km']:.0f}km | {target['weeks_out']}w out | "
        f"Phase: {target['training_phase']}"
        if target
        else "No A-race configured"
    )

    lines = [
        "=== ATHLETE STATE ===",
        f"CTL: {context['ctl']:.1f}  ATL: {context['atl']:.1f}  TSB: {context['tsb']:.1f}",
        f"ACWR: {context['acwr']:.2f}  30-day TSS avg: {context['tss_30d_avg']:.1f}",
        f"LTHR: {context['lthr']} bpm  Threshold pace: {threshold_pace_min:.1f} min/km",
        f"Training phase: {context['training_phase']}",
        f"Race target: {race_str}",
        "",
        "=== TODAY'S SESSION ===",
        f"Activity: {activity['activity_name']} ({activity['sport_type']})",
        f"Duration: {dur_min} min  Distance: {dist_km:.1f} km  Elevation: {elev:.0f} m D+",
        f"hrTSS: {activity['hr_tss']:.1f}  (vs 30d avg {context['tss_30d_avg']:.1f})",
        f"HR drift: {activity['hr_drift_pct']:.1f}%  Aerobic decoupling: {activity['aerobic_decoupling_pct']:.1f}%",
        f"NGP: {ngp_min:.2f} min/km  (threshold: {threshold_pace_min:.1f} min/km)",
        f"Cadence: {cadence_str}",
        f"Zones: {zones_str}",
    ]

    planned_today = context.get("planned_today")
    if planned_today:
        lines += [
            "",
            "=== PLANNED WORKOUT (today) ===",
            f"Type: {planned_today['workout_type']}",
            _planned_numbers_line(planned_today),
        ]
        if planned_today.get("description"):
            lines.append(f"Description: {planned_today['description']}")

    planned_tomorrow = context.get("planned_tomorrow")
    if planned_tomorrow:
        lines += [
            "",
            "=== PLANNED TOMORROW ===",
            f"Type: {planned_tomorrow['workout_type']}  "
            + _planned_summary_line(planned_tomorrow),
        ]

    lines += [
        "",
        "Diagnose this session. Be specific with numbers. Output via submit_debrief tool.",
    ]
    return "\n".join(lines)


def _planned_numbers_line(plan: dict) -> str:
    parts = []
    if plan.get("planned_tss") is not None:
        parts.append(f"Planned TSS: {plan['planned_tss']:.0f}")
    if plan.get("planned_duration_min") is not None:
        parts.append(f"Duration: {plan['planned_duration_min']} min")
    if plan.get("planned_distance_km") is not None:
        parts.append(f"Distance: {plan['planned_distance_km']:.0f} km")
    if plan.get("planned_elevation_m") is not None:
        parts.append(f"D+: {plan['planned_elevation_m']} m")
    return "   ".join(parts) if parts else "(no numeric targets)"


def _planned_summary_line(plan: dict) -> str:
    parts = []
    if plan.get("planned_tss") is not None:
        parts.append(f"Planned TSS: {plan['planned_tss']:.0f}")
    if plan.get("planned_duration_min") is not None:
        parts.append(f"Duration: {plan['planned_duration_min']} min")
    return "  ".join(parts) if parts else "(no numeric targets)"
```

- [ ] **Step 5: Run prompt tests**

Run: `cd backend && pytest tests/test_agents/test_prompts_planned.py -v`
Expected: 4 passed.

- [ ] **Step 6: Run full suite**

Run: `cd backend && pytest tests/ -x -q`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/prompts.py backend/tests/test_agents/test_prompts_planned.py
git commit -m "feat: PLAN VS ACTUAL prompt section + conditional planned prompt blocks"
```

---

## Task 11: Extend `submit_debrief` tool + fallback compliance scoring

**Files:**
- Modify: `backend/app/agents/debrief_graph.py`
- Create: `backend/tests/test_agents/test_compliance_fallback.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_agents/test_compliance_fallback.py`:

```python
from datetime import date

from app.agents.debrief_graph import compute_plan_compliance
from app.agents.schema import PlannedWorkoutContext


def _planned(workout_type: str, tss: float | None, duration: int | None) -> PlannedWorkoutContext:
    return PlannedWorkoutContext(
        date=date(2026, 4, 22),
        workout_type=workout_type,
        planned_tss=tss,
        planned_duration_min=duration,
    )


def test_perfect_match_scores_high():
    planned = _planned("easy", 50, 45)
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=50,
        actual_duration_min=45,
        zone_distribution={"z3_pct": 5, "z4_pct": 2, "z5_pct": 0},
    )
    assert score >= 95
    assert headline == "On target."


def test_overcooked_easy_day_penalises_type_break_and_tss():
    planned = _planned("easy", 50, 45)
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=120,        # 240% of 50 → delta 1.40, clamped to 1.0 → -40
        actual_duration_min=55, # 22% over  → -6.6
        zone_distribution={"z3_pct": 30, "z4_pct": 15, "z5_pct": 5},  # Z3-5 = 50% → type break (-30)
    )
    assert score <= 30
    assert "Overcooked" in headline


def test_undertrained_day():
    planned = _planned("long", 180, 240)
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=60,          # 33% of planned → -26.8
        actual_duration_min=80, # 33% of planned → -20
        zone_distribution={"z3_pct": 5, "z4_pct": 1, "z5_pct": 0},
    )
    # Long + duration < 75% planned = TYPE BREAK
    assert score <= 40
    assert ("underdelivered" in headline.lower()) or ("TYPE BREAK" in headline)


def test_skipped_quality_session_type_break():
    planned = _planned("interval", 95, 75)
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=55,
        actual_duration_min=70,
        zone_distribution={"z3_pct": 3, "z4_pct": 1, "z5_pct": 0},  # Z3-5 = 4% → skipped quality
    )
    assert "TYPE BREAK" in headline or "quality" in headline.lower()
    assert score < 80


def test_missing_planned_numbers_still_scores_type_axis():
    planned = _planned("recovery", None, None)
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=120,
        actual_duration_min=90,
        zone_distribution={"z3_pct": 25, "z4_pct": 10, "z5_pct": 5},
    )
    # No TSS or duration penalties possible; type break = -30
    assert score == 70


def test_compliance_string_format_matches_contract():
    from app.agents.debrief_graph import format_plan_compliance_string

    planned = _planned("easy", 50, 45)
    result = format_plan_compliance_string(
        planned=planned,
        actual_tss=50,
        actual_duration_min=45,
        zone_distribution={"z3_pct": 5, "z4_pct": 2, "z5_pct": 0},
    )
    assert result.startswith("100/100 ") or result.startswith("99/100 ") or result.startswith("98/100 ")
    assert len(result.split(" ", 1)[1]) > 0
```

- [ ] **Step 2: Run tests — fail**

Run: `cd backend && pytest tests/test_agents/test_compliance_fallback.py -v`

- [ ] **Step 3: Add tool field and scoring function to `debrief_graph.py`**

First, extend the `_DEBRIEF_TOOL` in `backend/app/agents/debrief_graph.py`. Find the existing properties dict and add:

```python
"plan_compliance": {
    "type": "string",
    "description": (
        "Only when the prompt contains [PLANNED WORKOUT (today)]. "
        "Start with '<0-100>/100 ' then one sentence. "
        "Emit empty string if no plan block present."
    ),
},
```

`plan_compliance` is NOT added to the `required` array — it's optional.

Then append new helpers at the bottom of `debrief_graph.py`:

```python
# ---------------------------------------------------------------------------
# Plan-vs-actual fallback scoring
# ---------------------------------------------------------------------------

from app.agents.schema import PlannedWorkoutContext


QUALITY_TYPES = frozenset({"tempo", "interval", "hill"})
EASY_TYPES = frozenset({"recovery", "easy"})


def compute_plan_compliance(
    *,
    planned: PlannedWorkoutContext,
    actual_tss: float,
    actual_duration_min: float,
    zone_distribution: dict[str, float],
) -> tuple[int, str]:
    """Return (score 0-100, headline sentence). Spec: see design doc §
    'Fallback scoring formula'."""
    score: float = 100.0

    # TSS axis — up to -40
    if planned.planned_tss and actual_tss and planned.planned_tss > 0:
        delta = abs(actual_tss - planned.planned_tss) / planned.planned_tss
        score -= min(delta, 1.0) * 40

    # Duration axis — up to -30
    if (
        planned.planned_duration_min
        and actual_duration_min
        and planned.planned_duration_min > 0
    ):
        delta = abs(actual_duration_min - planned.planned_duration_min) / planned.planned_duration_min
        score -= min(delta, 1.0) * 30

    # Type fidelity axis — flat -30
    type_break, type_reason = _detect_type_break(
        planned=planned,
        actual_duration_min=actual_duration_min,
        zone_distribution=zone_distribution,
    )
    if type_break:
        score -= 30

    score_int = max(0, round(score))

    # Headline priority: TYPE BREAK > overcooked > underdelivered > on target
    headline = _pick_headline(
        planned=planned,
        actual_tss=actual_tss,
        actual_duration_min=actual_duration_min,
        type_break=type_break,
        type_reason=type_reason,
    )
    return score_int, headline


def _detect_type_break(
    *,
    planned: PlannedWorkoutContext,
    actual_duration_min: float,
    zone_distribution: dict[str, float],
) -> tuple[bool, str]:
    z_hard = (
        zone_distribution.get("z3_pct", 0.0)
        + zone_distribution.get("z4_pct", 0.0)
        + zone_distribution.get("z5_pct", 0.0)
    )
    if planned.workout_type in EASY_TYPES and z_hard > 20:
        return True, "ran hard on an easy day"
    if planned.workout_type in QUALITY_TYPES and z_hard < 15:
        return True, "skipped the planned quality"
    if (
        planned.workout_type == "long"
        and planned.planned_duration_min
        and actual_duration_min < planned.planned_duration_min * 0.75
    ):
        return True, "cut the long run short"
    return False, ""


def _pick_headline(
    *,
    planned: PlannedWorkoutContext,
    actual_tss: float,
    actual_duration_min: float,
    type_break: bool,
    type_reason: str,
) -> str:
    if type_break:
        return f"TYPE BREAK — {type_reason}."
    if (
        planned.planned_tss
        and actual_tss > planned.planned_tss * 1.20
        and planned.workout_type in EASY_TYPES
    ):
        return "Overcooked an easy day — tomorrow's quality session is now at risk."
    if (
        planned.planned_tss
        and actual_tss < planned.planned_tss * 0.80
        and actual_duration_min > 10
    ):
        return "Plan underdelivered — diagnose why (HR drift, RPE, life stress, weather)."
    return "On target."


def format_plan_compliance_string(
    *,
    planned: PlannedWorkoutContext,
    actual_tss: float,
    actual_duration_min: float,
    zone_distribution: dict[str, float],
) -> str:
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=actual_tss,
        actual_duration_min=actual_duration_min,
        zone_distribution=zone_distribution,
    )
    return f"{score}/100 {headline}"
```

- [ ] **Step 4: Wire fallback into `fallback_debrief` and the LLM path**

Still in `debrief_graph.py`, update `fallback_debrief` to populate `plan_compliance` when context has `planned_today`:

Replace:

```python
def fallback_debrief(activity: ActivityInput, context: AthleteContext) -> DebriefOutput:
    return DebriefOutput(
        load_verdict=_load_verdict(activity, context),
        technical_insight=_technical_insight(activity),
        next_session_action=_next_session_action(context),
        nutrition_protocol=_nutrition_protocol(activity),
        vmm_projection=_vmm_projection(context),
    )
```

With:

```python
def fallback_debrief(activity: ActivityInput, context: AthleteContext) -> DebriefOutput:
    plan_compliance = ""
    if context.planned_today is not None:
        plan_compliance = format_plan_compliance_string(
            planned=context.planned_today,
            actual_tss=activity.hr_tss or activity.tss,
            actual_duration_min=activity.duration_sec / 60,
            zone_distribution=activity.zone_distribution,
        )

    return DebriefOutput(
        load_verdict=_load_verdict(activity, context),
        technical_insight=_technical_insight(activity),
        next_session_action=_next_session_action(context),
        nutrition_protocol=_nutrition_protocol(activity),
        vmm_projection=_vmm_projection(context),
        plan_compliance=plan_compliance,
    )
```

Also, in the LLM path, guarantee the field is always in the returned dict (Claude may omit it). Find `_llm_debrief` and change the successful return to:

```python
            result: dict[str, str] = block.input  # type: ignore[assignment]
            combined = " ".join(result.values()).lower()
            if any(phrase in combined for phrase in GENERIC_PHRASES):
                logger.warning("LLM output contained generic phrase — falling back")
                return fallback_debrief(activity, context).model_dump()
            # Back-fill plan_compliance deterministically when the LLM
            # omitted it despite a plan being present. This keeps the
            # frontend badge parser reliable.
            if context.planned_today is not None and not result.get("plan_compliance"):
                result["plan_compliance"] = format_plan_compliance_string(
                    planned=context.planned_today,
                    actual_tss=activity.hr_tss or activity.tss,
                    actual_duration_min=activity.duration_sec / 60,
                    zone_distribution=activity.zone_distribution,
                )
            result.setdefault("plan_compliance", "")
            return result
```

- [ ] **Step 5: Run all agent tests**

Run: `cd backend && pytest tests/test_agents/ -v`
Expected: compliance fallback tests pass (6 new), existing agent tests still green.

- [ ] **Step 6: Run full suite**

Run: `cd backend && pytest tests/ -x -q`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/debrief_graph.py backend/tests/test_agents/test_compliance_fallback.py
git commit -m "feat: plan_compliance tool field + deterministic fallback scoring"
```

---

## Task 12: Fire-and-forget sync before activity processing

**Files:**
- Modify: `backend/app/services/activity_ingestion.py`
- Create: `backend/tests/test_services/test_activity_ingestion_autosync.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_services/test_activity_ingestion_autosync.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.services.activity_ingestion import maybe_autosync_plan


@pytest.mark.asyncio
async def test_autosync_skipped_when_no_url(db_session: AsyncSession, monkeypatch):
    athlete = Athlete(strava_athlete_id=1)
    db_session.add(athlete)
    await db_session.commit()

    called = False

    async def fake_sync(_athlete_id, _db):
        nonlocal called
        called = True
        raise AssertionError("should not be called")

    monkeypatch.setattr("app.services.activity_ingestion.sync_plan", fake_sync)
    await maybe_autosync_plan(db_session, athlete.id)
    assert called is False


@pytest.mark.asyncio
async def test_autosync_invoked_when_url_configured(
    db_session: AsyncSession, monkeypatch
):
    from app.services.plan_import import SyncReport

    athlete = Athlete(
        strava_athlete_id=1,
        plan_sheet_url="https://docs.google.com/spreadsheets/d/x/pub?output=csv",
    )
    db_session.add(athlete)
    await db_session.commit()

    called = False

    async def fake_sync(_athlete_id, _db):
        nonlocal called
        called = True
        return SyncReport(status="ok", fetched_rows=1, accepted=1)

    monkeypatch.setattr("app.services.activity_ingestion.sync_plan", fake_sync)
    await maybe_autosync_plan(db_session, athlete.id)
    assert called is True


@pytest.mark.asyncio
async def test_autosync_swallows_exceptions(
    db_session: AsyncSession, monkeypatch
):
    athlete = Athlete(
        strava_athlete_id=1,
        plan_sheet_url="https://docs.google.com/spreadsheets/d/x/pub?output=csv",
    )
    db_session.add(athlete)
    await db_session.commit()

    async def fake_sync(_athlete_id, _db):
        raise RuntimeError("network down")

    monkeypatch.setattr("app.services.activity_ingestion.sync_plan", fake_sync)
    # Must not raise
    await maybe_autosync_plan(db_session, athlete.id)
```

- [ ] **Step 2: Run tests — fail (maybe_autosync_plan does not exist)**

Run: `cd backend && pytest tests/test_services/test_activity_ingestion_autosync.py -v`

- [ ] **Step 3: Add `maybe_autosync_plan` and wire into `process_activity_metrics`**

In `backend/app/services/activity_ingestion.py`, add near the top imports:

```python
from app.services.plan_import import sync_plan
```

Add a new helper near `_build_athlete_context`:

```python
async def maybe_autosync_plan(session: AsyncSession, athlete_id: int) -> None:
    """Trigger a plan sync if the athlete has a sheet configured.
    Failures are logged and swallowed — plan sync must never block
    activity processing."""
    from app.models.athlete import Athlete

    athlete = await session.get(Athlete, athlete_id)
    if athlete is None or not athlete.plan_sheet_url:
        return
    try:
        await sync_plan(athlete_id, session)
    except Exception:
        logger.warning(
            "plan autosync failed for athlete %s", athlete_id, exc_info=True
        )
```

Then in `process_activity_metrics`, invoke it right before `_build_athlete_context`:

Find:

```python
    profile = await _find_profile(session, activity.athlete_id)
    metrics, values = _compute_metrics(activity, profile)
    context = await _build_athlete_context(session, activity.athlete_id, profile)
```

Replace (note: `activity_date` was already wired in Task 9):

```python
    profile = await _find_profile(session, activity.athlete_id)
    metrics, values = _compute_metrics(activity, profile)
    await maybe_autosync_plan(session, activity.athlete_id)
    activity_date = activity.start_date.date() if activity.start_date else None
    context = await _build_athlete_context(
        session, activity.athlete_id, profile, activity_date=activity_date
    )
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_services/test_activity_ingestion_autosync.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run full suite**

Run: `cd backend && pytest tests/ -x -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/activity_ingestion.py backend/tests/test_services/test_activity_ingestion_autosync.py
git commit -m "feat: fire-and-forget plan sync before building activity context"
```

---

## Task 13: Frontend types + API client additions

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add types**

Append to `frontend/src/types/index.ts`:

```typescript
export type WorkoutType =
  | "recovery"
  | "easy"
  | "long"
  | "tempo"
  | "interval"
  | "hill"
  | "race"
  | "rest"
  | "cross"
  | "strength"

export interface PlanEntry {
  date: string  // ISO YYYY-MM-DD
  workout_type: WorkoutType
  planned_tss: number | null
  planned_duration_min: number | null
  planned_distance_km: number | null
  planned_elevation_m: number | null
  description: string | null
}

export interface PlanConfig {
  athlete_id: number
  sheet_url: string | null
  plan_synced_at: string | null
}

export interface SyncReportRow {
  row_number: number
  reason: string
}

export interface SyncReport {
  status: "ok" | "failed"
  fetched_rows: number
  accepted: number
  rejected: SyncReportRow[]
  error: string | null
}
```

Also extend `Debrief` to include the new field:

```typescript
export interface Debrief {
  load_verdict: string
  technical_insight: string
  next_session_action: string
  nutrition_protocol?: string
  vmm_projection?: string
  plan_compliance?: string   // "NN/100 <sentence>" or ""
}
```

- [ ] **Step 2: Add API functions**

Append to `frontend/src/api/client.ts` (before `request()` helper):

```typescript
import type { PlanConfig, PlanEntry, SyncReport } from "../types"

export const PLAN_TEMPLATE_SHEET_URL =
  "https://docs.google.com/spreadsheets/d/your-template-id/edit"
// TODO(post-MVP): serve this from the backend so we can change it
//                 without a frontend deploy. Tracked in spec open question #3.

export async function putPlanConfig(params: {
  athleteId: number
  sheetUrl: string
}): Promise<PlanConfig> {
  return request(
    api.put("/plan/config", {
      athlete_id: params.athleteId,
      sheet_url: params.sheetUrl,
    }),
  )
}

export async function deletePlanConfig(athleteId: number): Promise<void> {
  await request(api.delete(`/plan/config?athlete_id=${athleteId}`))
}

export async function syncPlan(athleteId: number): Promise<SyncReport> {
  return request(api.post("/plan/sync", { athlete_id: athleteId }))
}

export async function getPlanRange(params: {
  athleteId: number
  from: string   // YYYY-MM-DD
  to: string
}): Promise<PlanEntry[]> {
  return request(
    api.get(
      `/plan?athlete_id=${params.athleteId}&from_=${params.from}&to=${params.to}`,
    ),
  )
}
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/client.ts
git commit -m "feat: frontend types + api client for plan config/sync/range"
```

---

## Task 14: Targets page — "Training Plan" section

**Files:**
- Modify: `frontend/src/pages/Targets.tsx`

- [ ] **Step 1: Add the section component**

At the bottom of `frontend/src/pages/Targets.tsx`, before the last closing brace of the file, append the following. Then render it inside `TargetsView`.

First add imports at the top:

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createRaceTarget,
  deleteRaceTarget,
  deletePlanConfig,
  getStoredAthleteId,
  listRaceTargets,
  PLAN_TEMPLATE_SHEET_URL,
  putPlanConfig,
  requireAthleteId,
  syncPlan,
} from "../api/client"
import type {
  RacePriority,
  RaceTarget,
  RaceTargetPayload,
  SyncReport,
} from "../types"
```

Then change `TargetsView` to render the plan section beneath the two-column grid:

```typescript
function TargetsView({ athleteId }: { athleteId: number }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState(initialForm)
  const targets = useTargetsQuery(athleteId)
  const create = useCreateTarget(athleteId, queryClient, () => setForm(initialForm))
  const remove = useDeleteTarget(athleteId, queryClient)

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    create.mutate(toPayload(form, requireAthleteId(athleteId)))
  }

  return (
    <main className="min-h-screen bg-trail-surface px-4 py-8 text-trail-ink">
      <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[380px_1fr]">
        <TargetFormCard form={form} onChange={setForm} onSubmit={submit} />
        <TargetList isLoading={targets.isPending} onDelete={remove.mutate} targets={targets.data ?? []} />
      </div>
      <div className="mx-auto mt-6 max-w-6xl">
        <TrainingPlanCard athleteId={athleteId} />
      </div>
    </main>
  )
}
```

Add the `TrainingPlanCard` + helpers at the end of the file:

```typescript
function TrainingPlanCard({ athleteId }: { athleteId: number }) {
  const [sheetUrl, setSheetUrl] = useState("")
  const [localError, setLocalError] = useState<string | null>(null)
  const [lastReport, setLastReport] = useState<SyncReport | null>(null)

  const saveConfig = useMutation({
    mutationFn: (url: string) => putPlanConfig({ athleteId, sheetUrl: url }),
    onSuccess: () => setLocalError(null),
    onError: (err: unknown) =>
      setLocalError(err instanceof Error ? err.message : "save failed"),
  })

  const sync = useMutation({
    mutationFn: () => syncPlan(athleteId),
    onSuccess: (report) => setLastReport(report),
  })

  const unlink = useMutation({
    mutationFn: () => deletePlanConfig(athleteId),
    onSuccess: () => {
      setSheetUrl("")
      setLastReport(null)
    },
  })

  function onSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!isLikelyValidSheetUrl(sheetUrl)) {
      setLocalError(
        "URL must be a Google Sheets 'Publish to web → CSV' link.",
      )
      return
    }
    saveConfig.mutate(sheetUrl)
  }

  return (
    <Card
      className="rounded-lg shadow-panel border-slate-200"
      bordered={false}
    >
      <Typography.Title level={3} className="!mt-0 !mb-4 font-bold text-slate-950">
        Training plan
      </Typography.Title>
      <p className="mb-4 text-sm text-slate-600">
        Paste your Google Sheet's <em>Publish to the web → CSV</em> URL.
        The coach's weekly plan shows up on your dashboard and gets compared
        against every run you log.
      </p>
      <form className="space-y-3" onSubmit={onSave}>
        <TextField
          label="Google Sheets CSV URL"
          value={sheetUrl}
          onChange={setSheetUrl}
          placeholder="https://docs.google.com/spreadsheets/.../pub?output=csv"
        />
        <div className="flex gap-3">
          <Button
            type="primary"
            htmlType="submit"
            size="large"
            loading={saveConfig.isPending}
            className="bg-trail-strava font-bold"
          >
            Save
          </Button>
          <Button
            size="large"
            onClick={() => sync.mutate()}
            loading={sync.isPending}
            disabled={!sheetUrl && !saveConfig.data}
          >
            Sync now
          </Button>
          <Button
            danger
            size="large"
            onClick={() => unlink.mutate()}
            loading={unlink.isPending}
          >
            Unlink
          </Button>
        </div>
      </form>
      {localError ? (
        <p className="mt-3 text-sm font-medium text-red-600">{localError}</p>
      ) : null}
      {sync.isError ? (
        <p className="mt-3 text-sm font-medium text-red-600">
          Sync failed: {(sync.error as Error).message}
        </p>
      ) : null}
      {lastReport ? <SyncReportView report={lastReport} /> : null}
      <p className="mt-6 text-sm">
        <a
          href={PLAN_TEMPLATE_SHEET_URL}
          target="_blank"
          rel="noreferrer"
          className="font-semibold text-blue-700 hover:underline"
        >
          Copy the template sheet →
        </a>
      </p>
    </Card>
  )
}

function SyncReportView({ report }: { report: SyncReport }) {
  if (report.status === "failed") {
    return (
      <p className="mt-3 text-sm font-medium text-red-600">
        Sync failed: {report.error ?? "unknown error"}
      </p>
    )
  }
  return (
    <div className="mt-3 text-sm">
      <p className="font-semibold text-slate-800">
        Synced — {report.accepted} accepted, {report.rejected.length} rejected
        out of {report.fetched_rows} rows.
      </p>
      {report.rejected.length > 0 ? (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-red-700">
          {report.rejected.map((row) => (
            <li key={row.row_number}>
              row {row.row_number}: {row.reason}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

function isLikelyValidSheetUrl(url: string): boolean {
  return /^https:\/\/docs\.google\.com\/spreadsheets\/.+\/pub\?.*output=csv/i.test(url)
}
```

- [ ] **Step 2: Typecheck + build**

Run: `cd frontend && npm run typecheck`
Expected: no errors.

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Manual smoke**

Run: `cd frontend && npm run dev`
Open http://localhost:5173/targets. Verify the Training Plan card renders, validation fires on bad URL, and disabling the Sync button when nothing is typed feels right.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Targets.tsx
git commit -m "feat: Targets page — Training Plan section (save / sync / unlink)"
```

---

## Task 15: Dashboard — "This week (planned)" strip

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Read the current Dashboard to find the insertion point**

Before editing, read `frontend/src/pages/Dashboard.tsx` and identify the JSX node that renders the load chart. The strip should sit immediately above it.

- [ ] **Step 2: Add query + component**

Add at the top of `frontend/src/pages/Dashboard.tsx`:

```typescript
import { useQuery } from "@tanstack/react-query"
import { getPlanRange, getStoredAthleteId } from "../api/client"
import type { PlanEntry } from "../types"

function toIso(d: Date): string {
  return d.toISOString().slice(0, 10)
}

function usePlannedThisWeek(athleteId: number) {
  const today = new Date()
  const end = new Date()
  end.setDate(today.getDate() + 6)
  return useQuery({
    queryKey: ["plan-range", athleteId, toIso(today), toIso(end)],
    queryFn: () =>
      getPlanRange({
        athleteId,
        from: toIso(today),
        to: toIso(end),
      }),
  })
}

function ThisWeekStrip({ athleteId }: { athleteId: number }) {
  const query = usePlannedThisWeek(athleteId)
  const entries = query.data ?? []
  if (entries.length === 0) return null
  const byDate = new Map<string, PlanEntry>()
  for (const entry of entries) byDate.set(entry.date, entry)

  const today = new Date()
  const days: { label: string; iso: string; isToday: boolean }[] = []
  for (let i = 0; i < 7; i++) {
    const d = new Date()
    d.setDate(today.getDate() + i)
    const iso = toIso(d)
    days.push({
      label: i === 0 ? "Today" : d.toLocaleDateString("en-US", { weekday: "short" }),
      iso,
      isToday: i === 0,
    })
  }

  return (
    <section className="mb-4 rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        This week (planned)
      </h2>
      <div className="grid grid-cols-7 gap-2 text-center">
        {days.map((day) => {
          const entry = byDate.get(day.iso) ?? null
          return (
            <div
              className={
                "rounded border p-2 text-xs " +
                (day.isToday
                  ? "border-trail-strava bg-orange-50"
                  : "border-slate-200")
              }
              key={day.iso}
            >
              <p className="font-bold text-slate-800">{day.label}</p>
              <p className="mt-1 text-slate-700">
                {entry ? entry.workout_type : "—"}
              </p>
              <p className="mt-1 font-mono text-[11px] text-slate-500">
                {entry && entry.planned_tss !== null
                  ? `TSS ${entry.planned_tss.toFixed(0)}`
                  : ""}
              </p>
            </div>
          )
        })}
      </div>
    </section>
  )
}
```

- [ ] **Step 3: Render the strip**

Inside the Dashboard page component, immediately above the load chart JSX (identified in Step 1), insert:

```tsx
{athleteId !== null ? <ThisWeekStrip athleteId={athleteId} /> : null}
```

(Use whatever variable already holds the athlete id on this page. If none exists, add `const athleteId = getStoredAthleteId()` near the top of the page function.)

- [ ] **Step 4: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: no errors.

- [ ] **Step 5: Manual smoke**

Dev server → dashboard. Confirm the strip only appears once a plan is synced. Confirm Today is highlighted.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: Dashboard — This week (planned) strip"
```

---

## Task 16: ActivityDetail — "Planned vs Actual" block

**Files:**
- Modify: `frontend/src/pages/ActivityDetail.tsx`

- [ ] **Step 1: Read file to locate the DebriefCard render**

Before editing, open the file and find where `<DebriefCard ... />` is rendered. The new block goes directly above it.

- [ ] **Step 2: Add query + component**

Add imports:

```typescript
import { useQuery } from "@tanstack/react-query"
import { getPlanRange } from "../api/client"
import type { ActivityDetail, ActivityMetrics, Debrief, PlanEntry } from "../types"
```

Add this component at the bottom of the file:

```typescript
function PlannedVsActualBlock(props: {
  athleteId: number
  activity: ActivityDetail
  metrics: ActivityMetrics | null
  debrief: Debrief | null
}) {
  const iso = props.activity.start_date.slice(0, 10)
  const query = useQuery({
    queryKey: ["plan-range", props.athleteId, iso, iso],
    queryFn: () =>
      getPlanRange({ athleteId: props.athleteId, from: iso, to: iso }),
  })
  const entries: PlanEntry[] = query.data ?? []
  const planned = entries[0]
  if (!planned) return null

  const complianceText = props.debrief?.plan_compliance ?? ""
  const score = parseComplianceScore(complianceText)
  const sentence = stripComplianceScore(complianceText)

  const actualTss = props.metrics?.hr_tss ?? props.metrics?.tss ?? null
  const actualDurationMin = Math.round(props.activity.elapsed_time_sec / 60)

  return (
    <section className="mb-4 rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <header className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-bold text-slate-900">Planned vs actual</h2>
        {score !== null ? (
          <span
            className={
              "rounded-full px-3 py-1 text-sm font-bold " +
              complianceBadgeClasses(score)
            }
          >
            {score}/100
          </span>
        ) : null}
      </header>
      {sentence ? (
        <p className="mb-4 text-sm italic text-slate-700">&ldquo;{sentence}&rdquo;</p>
      ) : null}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500">
            <th className="pb-2"></th>
            <th className="pb-2">Planned</th>
            <th className="pb-2">Actual</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          <tr>
            <td className="py-2 font-semibold">Type</td>
            <td className="py-2">{planned.workout_type}</td>
            <td className="py-2">{props.activity.sport_type}</td>
          </tr>
          <tr>
            <td className="py-2 font-semibold">TSS</td>
            <td className="py-2">
              {planned.planned_tss !== null
                ? planned.planned_tss.toFixed(0)
                : "—"}
            </td>
            <td className="py-2">
              {actualTss !== null ? actualTss.toFixed(0) : "—"}
            </td>
          </tr>
          <tr>
            <td className="py-2 font-semibold">Duration</td>
            <td className="py-2">
              {planned.planned_duration_min !== null
                ? `${planned.planned_duration_min} min`
                : "—"}
            </td>
            <td className="py-2">{actualDurationMin} min</td>
          </tr>
          {planned.description ? (
            <tr>
              <td className="py-2 font-semibold">Notes</td>
              <td className="py-2" colSpan={2}>
                {planned.description}
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </section>
  )
}

function parseComplianceScore(text: string): number | null {
  const match = /^(\d{1,3})\/100\s/.exec(text)
  if (!match) return null
  const n = Number(match[1])
  return Number.isFinite(n) && n >= 0 && n <= 100 ? n : null
}

function stripComplianceScore(text: string): string {
  return text.replace(/^\d{1,3}\/100\s/, "").trim()
}

function complianceBadgeClasses(score: number): string {
  if (score >= 90) return "bg-green-100 text-green-800"
  if (score >= 70) return "bg-yellow-100 text-yellow-800"
  return "bg-red-100 text-red-800"
}
```

- [ ] **Step 3: Render it above DebriefCard**

Inside the ActivityDetail page's rendered JSX, directly above the `<DebriefCard ... />` line, add:

```tsx
{athleteId !== null ? (
  <PlannedVsActualBlock
    athleteId={athleteId}
    activity={detail.activity}
    metrics={detail.metrics}
    debrief={detail.debrief}
  />
) : null}
```

Adjust the exact variable names (`detail`, `athleteId`) to match the existing page — check the file for the active query result and athlete id source.

- [ ] **Step 4: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: green.

- [ ] **Step 5: Manual smoke**

Open an activity detail page for a date with a plan entry. Confirm block renders with badge colour matching the score. Open one WITHOUT a plan — confirm block is hidden.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ActivityDetail.tsx
git commit -m "feat: ActivityDetail — Planned vs Actual block with compliance badge"
```

---

## Task 17: End-to-end integration test

**Files:**
- Create: `backend/tests/test_services/test_plan_integration.py`

- [ ] **Step 1: Write the integration test**

`backend/tests/test_services/test_plan_integration.py`:

```python
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schema import ActivityInput, AthleteContext
from app.agents.debrief_graph import fallback_debrief
from app.models.activity import Activity
from app.models.athlete import Athlete, AthleteProfile
from app.services.activity_ingestion import _build_athlete_context, maybe_autosync_plan


CSV_BODY = """date,workout_type,planned_tss,planned_duration_min,planned_distance_km,planned_elevation_m,description
2026-04-22,easy,50,45,7,50,"HR cap LTHR-20, flat only"
2026-04-23,long,180,240,35,1200,"4h trail Z2"
"""


@pytest.mark.asyncio
async def test_sync_enrich_fallback_produces_compliance(
    db_session: AsyncSession, monkeypatch
):
    athlete = Athlete(
        strava_athlete_id=1,
        plan_sheet_url="https://docs.google.com/spreadsheets/d/x/pub?output=csv",
    )
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)

    async def fake_fetch(_url: str) -> str:
        return CSV_BODY

    monkeypatch.setattr("app.services.plan_import.fetch_plan_sheet", fake_fetch)

    # Autosync the plan (normally called before metrics processing)
    await maybe_autosync_plan(db_session, athlete.id)

    # Build context as if processing an activity on 2026-04-22
    context = await _build_athlete_context(
        db_session, athlete.id, profile=None, activity_date=date(2026, 4, 22)
    )
    assert context.planned_today is not None
    assert context.planned_today.workout_type == "easy"
    assert context.planned_tomorrow is not None
    assert context.planned_tomorrow.workout_type == "long"

    # Simulate an overcooked easy day: planned easy 50 TSS, actual long Z3-Z4
    activity = ActivityInput(
        activity_name="overcooked easy",
        duration_sec=90 * 60,
        distance_m=13000,
        sport_type="Run",
        tss=140,
        hr_tss=140,
        hr_drift_pct=7,
        aerobic_decoupling_pct=6,
        ngp_sec_km=330,
        zone_distribution={"z1_pct": 5, "z2_pct": 30, "z3_pct": 40, "z4_pct": 20, "z5_pct": 5},
        elevation_gain_m=200,
        cadence_avg=175,
    )

    debrief = fallback_debrief(activity, context)
    assert debrief.plan_compliance != ""
    assert debrief.plan_compliance.startswith(
        tuple(f"{i}/100 " for i in range(0, 101))
    )
    # Two axes failed (TSS +180%, TYPE BREAK on easy) → low score
    score = int(debrief.plan_compliance.split("/", 1)[0])
    assert score < 50


@pytest.mark.asyncio
async def test_no_plan_yields_empty_compliance(db_session: AsyncSession):
    athlete = Athlete(strava_athlete_id=1)
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)

    context = await _build_athlete_context(
        db_session, athlete.id, profile=None, activity_date=date(2026, 4, 22)
    )
    assert context.planned_today is None

    activity = ActivityInput(
        activity_name="normal",
        duration_sec=3600,
        distance_m=10000,
        sport_type="Run",
        tss=60,
        hr_tss=60,
        hr_drift_pct=3,
        aerobic_decoupling_pct=2,
        ngp_sec_km=360,
        zone_distribution={"z1_pct": 10, "z2_pct": 70, "z3_pct": 15, "z4_pct": 5, "z5_pct": 0},
        elevation_gain_m=100,
    )
    debrief = fallback_debrief(activity, context)
    assert debrief.plan_compliance == ""
```

- [ ] **Step 2: Run the integration test**

Run: `cd backend && pytest tests/test_services/test_plan_integration.py -v`
Expected: 2 passed.

- [ ] **Step 3: Run the whole suite**

Run: `cd backend && pytest tests/ -x -q`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_services/test_plan_integration.py
git commit -m "test: integration — sync → context enrichment → fallback compliance"
```

---

## Final verification

- [ ] **Backend full suite + type imports**

Run: `cd backend && pytest tests/ -x -q`
Expected: green.

- [ ] **Frontend typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: green.

- [ ] **Manual end-to-end smoke (post-merge task, not required for plan completion)**

1. Publish a real Google Sheet matching the template.
2. On /targets, paste the CSV URL → Save → Sync now.
3. Confirm sync report shows N accepted / 0 rejected.
4. Trigger a Strava webhook (or reprocess an existing activity that falls on a planned date).
5. Open the activity detail page → confirm the Planned vs Actual block renders with a badge.
6. Open /dashboard → confirm "This week (planned)" strip appears.

---

## Notes for the executor

- All backend tests use `sqlite+aiosqlite` in-memory (`conftest.py`), so the CHECK constraint on `workout_type` in Postgres does NOT apply in unit tests. Parser-level validation is what guards the enum in practice.
- The `_planned_numbers_line` helper falls back to `(no numeric targets)` when every numeric field is NULL — this matches the "rest" row in the sample CSV.
- If the LLM omits `plan_compliance` despite a plan being present, the back-fill in `_llm_debrief` guarantees the field is populated deterministically. The frontend always trusts the field.
- `get_planned_for_date` uses a direct SQL SELECT rather than relying on the relationship — this avoids lazy-load issues in the async session.
- The template sheet URL in `frontend/src/api/client.ts` is a TODO placeholder; replace `your-template-id` with the real shared template before manual smoke.
