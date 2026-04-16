import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete


def test_save_profile(
    client: TestClient, db_session: AsyncSession
) -> None:
    db_session.add(Athlete(id=1, strava_athlete_id=1001))
    asyncio.run(db_session.commit())
    response = client.post(
        "/onboarding/profile",
        json={
            "athlete_id": 1,
            "lthr": 162,
            "max_hr": 192,
            "threshold_pace_sec_km": 270,
            "weight_kg": 68.5,
            "units": "metric",
            "language": "en",
        },
    )
    assert response.status_code == 200
    assert response.json()["onboarding_complete"] is True
