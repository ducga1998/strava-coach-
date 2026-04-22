from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.training_plan import TrainingPlanEntry
from app.services.plan_import import import_csv_text, sync_plan


@pytest_asyncio.fixture
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
    # SQLite's DateTime(timezone=True) strips tzinfo on readback — treat the
    # naive value as UTC (which is what sync_plan stores). In Postgres this
    # is a no-op because TIMESTAMPTZ preserves tz.
    synced_at = athlete_with_sheet.plan_synced_at
    if synced_at.tzinfo is None:
        synced_at = synced_at.replace(tzinfo=timezone.utc)
    assert synced_at >= before


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


@pytest.mark.asyncio
async def test_import_csv_text_inserts_entries(
    db_session: AsyncSession, athlete_with_sheet: Athlete
):
    report = await import_csv_text(
        athlete_with_sheet.id, CSV_BODY_V1, db_session
    )

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
async def test_import_csv_text_updates_plan_synced_at(
    db_session: AsyncSession, athlete_with_sheet: Athlete
):
    before = datetime.now(timezone.utc)
    await import_csv_text(athlete_with_sheet.id, CSV_BODY_V1, db_session)
    await db_session.refresh(athlete_with_sheet)

    assert athlete_with_sheet.plan_synced_at is not None
    synced_at = athlete_with_sheet.plan_synced_at
    if synced_at.tzinfo is None:
        synced_at = synced_at.replace(tzinfo=timezone.utc)
    assert synced_at >= before


@pytest.mark.asyncio
async def test_import_csv_text_preserves_plan_sheet_url(
    db_session: AsyncSession, athlete_with_sheet: Athlete
):
    original_url = athlete_with_sheet.plan_sheet_url
    await import_csv_text(athlete_with_sheet.id, CSV_BODY_V1, db_session)
    await db_session.refresh(athlete_with_sheet)
    assert athlete_with_sheet.plan_sheet_url == original_url


@pytest.mark.asyncio
async def test_import_csv_text_unknown_athlete(db_session: AsyncSession):
    report = await import_csv_text(999_999, CSV_BODY_V1, db_session)
    assert report.status == "failed"
    assert "not found" in (report.error or "").lower()


@pytest.mark.asyncio
async def test_import_csv_text_malformed_header(
    db_session: AsyncSession, athlete_with_sheet: Athlete
):
    bad_csv = "foo,bar\n1,2\n"
    report = await import_csv_text(
        athlete_with_sheet.id, bad_csv, db_session
    )
    assert report.status == "failed"
    assert "missing required column" in (report.error or "").lower()


@pytest.mark.asyncio
async def test_import_csv_text_upserts_like_sync(
    db_session: AsyncSession, athlete_with_sheet: Athlete
):
    await import_csv_text(athlete_with_sheet.id, CSV_BODY_V1, db_session)
    report = await import_csv_text(
        athlete_with_sheet.id, CSV_BODY_V2, db_session
    )
    assert report.status == "ok"
    assert report.accepted == 3

    rows = (
        await db_session.execute(
            select(TrainingPlanEntry).where(
                TrainingPlanEntry.athlete_id == athlete_with_sheet.id
            )
        )
    ).scalars().all()
    assert len(rows) == 3  # 2 updated + 1 new — not 5
    long_row = next(r for r in rows if r.date == date(2026, 4, 22))
    assert long_row.planned_tss == 200
    assert "v2" in (long_row.description or "")


@pytest.mark.asyncio
async def test_import_csv_text_rejected_rows_in_report(
    db_session: AsyncSession, athlete_with_sheet: Athlete
):
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        "2026-04-22,fartlek,60,45,7,,\n"  # invalid workout_type
        "2026-04-23,easy,50,40,6,,\n"
    )
    report = await import_csv_text(
        athlete_with_sheet.id, csv, db_session
    )
    assert report.status == "ok"
    assert report.accepted == 1
    assert len(report.rejected) == 1
    assert report.rejected[0].row_number == 2
