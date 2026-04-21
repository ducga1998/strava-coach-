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
