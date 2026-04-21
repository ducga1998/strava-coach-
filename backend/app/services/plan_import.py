"""Training plan CSV import — pure parser, fetcher, sync orchestrator.

Parser is pure (no I/O). Fetcher + sync functions are added in later tasks.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Literal

import httpx
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.training_plan import WORKOUT_TYPES, TrainingPlanEntry

if TYPE_CHECKING:
    from app.agents.schema import PlannedWorkoutContext


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
        raise _RowReject(f"date '{date_s}' is not ISO YYYY-MM-DD") from None

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
        raise _RowReject(f"{field_name} '{raw}' is not numeric") from None


def _parse_optional_int(raw: str, field_name: str) -> int | None:
    if raw == "":
        return None
    try:
        return int(float(raw))  # tolerate "180.0"
    except ValueError:
        raise _RowReject(f"{field_name} '{raw}' is not numeric") from None


SHEET_URL_REGEX = re.compile(
    r"^https://docs\.google\.com/spreadsheets/.+/pub\?.*output=csv.*$",
    re.IGNORECASE,
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
