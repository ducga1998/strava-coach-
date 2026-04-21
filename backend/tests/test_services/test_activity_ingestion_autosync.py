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
