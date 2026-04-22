"""PATCH /athletes/{id}/language — validation, success, 404s, no side effects."""
import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete, AthleteProfile


def _seed(db_session: AsyncSession, *, onboarded: bool = True) -> None:
    db_session.add(Athlete(id=1, strava_athlete_id=1001))
    db_session.add(
        AthleteProfile(
            athlete_id=1,
            lthr=162,
            max_hr=192,
            threshold_pace_sec_km=270,
            language="en",
            onboarding_complete=onboarded,
        )
    )
    asyncio.run(db_session.commit())


def test_update_language_to_vi_succeeds(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed(db_session)
    response = client.patch("/athletes/1/language", json={"language": "vi"})
    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "vi"
    # Onboarding status untouched.
    assert body["onboarding_complete"] is True


def test_update_language_back_to_en(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed(db_session)
    client.patch("/athletes/1/language", json={"language": "vi"})
    response = client.patch("/athletes/1/language", json={"language": "en"})
    assert response.status_code == 200
    assert response.json()["language"] == "en"


def test_update_language_rejects_unknown_code(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed(db_session)
    response = client.patch("/athletes/1/language", json={"language": "fr"})
    assert response.status_code == 422


def test_update_language_unknown_athlete(
    client: TestClient, db_session: AsyncSession
) -> None:
    response = client.patch("/athletes/999/language", json={"language": "vi"})
    assert response.status_code == 404


def test_update_language_without_profile(
    client: TestClient, db_session: AsyncSession
) -> None:
    db_session.add(Athlete(id=2, strava_athlete_id=2002))
    asyncio.run(db_session.commit())
    response = client.patch("/athletes/2/language", json={"language": "vi"})
    assert response.status_code == 404


def test_get_athlete_exposes_language(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed(db_session)
    response = client.get("/athletes/1")
    assert response.status_code == 200
    assert response.json()["profile"]["language"] == "en"
