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
        f"/plan?athlete_id={athlete.id}&from=2026-04-22&to=2026-04-30"
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


SMALL_CSV = (
    "date,workout_type,planned_tss,planned_duration_min,"
    "planned_distance_km,planned_elevation_m,description\n"
    "2026-04-22,long,180,240,35,1200,long run\n"
)


def test_post_import_csv_inserts_rows(
    client: TestClient, db_session: AsyncSession
):
    import asyncio

    athlete = asyncio.run(_make_athlete(db_session, strava_id=201))
    response = client.post(
        "/plan/import-csv",
        json={"athlete_id": athlete.id, "csv_text": SMALL_CSV},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["accepted"] == 1
    assert body["rejected"] == []


def test_post_import_csv_rejects_empty_body(
    client: TestClient, db_session: AsyncSession
):
    import asyncio

    athlete = asyncio.run(_make_athlete(db_session, strava_id=202))
    response = client.post(
        "/plan/import-csv",
        json={"athlete_id": athlete.id, "csv_text": ""},
    )
    assert response.status_code == 422


def test_post_import_csv_rejects_oversize_body(
    client: TestClient, db_session: AsyncSession
):
    import asyncio

    athlete = asyncio.run(_make_athlete(db_session, strava_id=203))
    oversize = "x" * 200_001
    response = client.post(
        "/plan/import-csv",
        json={"athlete_id": athlete.id, "csv_text": oversize},
    )
    assert response.status_code == 422


def test_post_import_csv_unknown_athlete(client: TestClient):
    response = client.post(
        "/plan/import-csv",
        json={"athlete_id": 999_999, "csv_text": SMALL_CSV},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert "not found" in (body["error"] or "").lower()


def test_put_plan_config_accepts_edit_url(
    client: TestClient, db_session: AsyncSession
):
    import asyncio

    athlete = asyncio.run(_make_athlete(db_session, strava_id=204))
    edit_url = "https://docs.google.com/spreadsheets/d/abc123/edit?gid=7"
    response = client.put(
        "/plan/config",
        json={"athlete_id": athlete.id, "sheet_url": edit_url},
    )
    assert response.status_code == 200, response.text
    assert response.json()["sheet_url"] == edit_url  # stored as-is
