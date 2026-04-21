"""Tests for `enqueue_plan_sync` — the plan-autosync worker task that runs
on an ISOLATED DB session so it can't interfere with whatever transaction
(e.g. activity ingestion) is in flight on the caller's session.
"""
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete


def _patch_session_factory(monkeypatch, session: AsyncSession) -> None:
    """Route `app.workers.tasks.get_session_factory()()` back to the test's
    `db_session` so the worker reads/writes the same in-memory DB.

    `get_session_factory()` returns an async_sessionmaker; calling the maker
    returns an AsyncSession which is also an async context manager. We fake
    both layers so the production code path (`async with
    get_session_factory()() as s: ...`) hands back our test session.
    """
    @asynccontextmanager
    async def _cm():
        yield session

    maker = MagicMock(side_effect=lambda: _cm())
    factory = MagicMock(return_value=maker)
    monkeypatch.setattr("app.workers.tasks.get_session_factory", factory)


@pytest.mark.asyncio
async def test_enqueue_plan_sync_skipped_when_no_url(
    db_session: AsyncSession, monkeypatch
):
    from app.workers.tasks import enqueue_plan_sync

    athlete = Athlete(strava_athlete_id=1)
    db_session.add(athlete)
    await db_session.commit()

    _patch_session_factory(monkeypatch, db_session)

    called = False

    async def fake_sync(_athlete_id, _session):
        nonlocal called
        called = True
        raise AssertionError("should not be called when plan_sheet_url is None")

    monkeypatch.setattr("app.workers.tasks.sync_plan", fake_sync)
    await enqueue_plan_sync(athlete.id)
    assert called is False


@pytest.mark.asyncio
async def test_enqueue_plan_sync_invoked_when_url_configured(
    db_session: AsyncSession, monkeypatch
):
    from app.services.plan_import import SyncReport
    from app.workers.tasks import enqueue_plan_sync

    athlete = Athlete(
        strava_athlete_id=1,
        plan_sheet_url="https://docs.google.com/spreadsheets/d/x/pub?output=csv",
    )
    db_session.add(athlete)
    await db_session.commit()

    _patch_session_factory(monkeypatch, db_session)

    call_ids: list[int] = []

    async def fake_sync(athlete_id, _session):
        call_ids.append(athlete_id)
        return SyncReport(status="ok", fetched_rows=1, accepted=1)

    monkeypatch.setattr("app.workers.tasks.sync_plan", fake_sync)
    await enqueue_plan_sync(athlete.id)
    assert call_ids == [athlete.id]


@pytest.mark.asyncio
async def test_enqueue_plan_sync_swallows_exceptions(
    db_session: AsyncSession, monkeypatch
):
    from app.workers.tasks import enqueue_plan_sync

    athlete = Athlete(
        strava_athlete_id=1,
        plan_sheet_url="https://docs.google.com/spreadsheets/d/x/pub?output=csv",
    )
    db_session.add(athlete)
    await db_session.commit()

    _patch_session_factory(monkeypatch, db_session)

    async def fake_sync(_athlete_id, _session):
        raise RuntimeError("network down")

    monkeypatch.setattr("app.workers.tasks.sync_plan", fake_sync)

    # Must not raise — the autosync is best-effort and errors are logged.
    await enqueue_plan_sync(athlete.id)


@pytest.mark.asyncio
async def test_enqueue_plan_sync_does_not_touch_callers_session(
    db_session: AsyncSession, monkeypatch
):
    """The caller's session (here `db_session`) must remain usable after
    autosync completes or fails — no poisoning, no lost state. Because
    `enqueue_plan_sync` uses its own isolated session, this is an invariant
    by construction; this test locks it against re-introduction of the
    shared-session anti-pattern.
    """
    from app.workers.tasks import enqueue_plan_sync

    # Pre-seed an athlete on the caller's session to exercise the path where
    # autosync might have touched the shared session (it must not).
    athlete = Athlete(
        strava_athlete_id=1,
        plan_sheet_url="https://docs.google.com/spreadsheets/d/x/pub?output=csv",
    )
    db_session.add(athlete)
    await db_session.commit()

    # Use a DIFFERENT session for the autosync — monkeypatch factory to
    # yield a fresh session created from the same engine.
    from sqlalchemy.ext.asyncio import async_sessionmaker

    autosync_session_maker = async_sessionmaker(
        db_session.bind, expire_on_commit=False
    )

    @asynccontextmanager
    async def _cm():
        async with autosync_session_maker() as s:
            yield s

    maker = MagicMock(side_effect=lambda: _cm())
    factory = MagicMock(return_value=maker)
    monkeypatch.setattr("app.workers.tasks.get_session_factory", factory)

    async def fake_sync(_athlete_id, _session):
        raise RuntimeError("simulated failure in isolated session")

    monkeypatch.setattr("app.workers.tasks.sync_plan", fake_sync)

    await enqueue_plan_sync(athlete.id)

    # The caller's session is still usable: write + commit must succeed.
    another = Athlete(strava_athlete_id=999)
    db_session.add(another)
    await db_session.commit()
