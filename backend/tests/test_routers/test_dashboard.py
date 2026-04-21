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
