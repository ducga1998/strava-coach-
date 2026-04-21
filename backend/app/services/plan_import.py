"""Training plan CSV import — pure parser, fetcher, sync orchestrator.

Parser is pure (no I/O). Fetcher + sync functions are added in later tasks.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

import httpx
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
