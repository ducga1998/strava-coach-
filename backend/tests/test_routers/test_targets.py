import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete


def test_create_and_list_target(
    client: TestClient, db_session: AsyncSession
) -> None:
    db_session.add(Athlete(id=1, strava_athlete_id=1001))
    asyncio.run(db_session.commit())
    response = client.post(
        "/targets/",
        json={
            "athlete_id": 1,
            "race_name": "VMM 100",
            "race_date": "2026-11-15",
            "distance_km": 100.0,
            "elevation_gain_m": 8000,
            "priority": "A",
        },
    )
    assert response.status_code == 201
    target_id = response.json()["id"]

    listed = client.get("/targets/?athlete_id=1")
    assert listed.status_code == 200
    ids = [target["id"] for target in listed.json()]
    assert target_id in ids
