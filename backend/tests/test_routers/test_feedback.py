import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.feedback import UserFeedback


def _seed_athlete_and_activity(db_session: AsyncSession) -> tuple[Athlete, Activity]:
    async def _seed() -> tuple[Athlete, Activity]:
        athlete = Athlete(id=1, strava_athlete_id=1001)
        db_session.add(athlete)
        await db_session.flush()
        activity = Activity(
            id=42,
            athlete_id=1,
            strava_activity_id=9876543210,
            name="Morning Run",
            sport_type="Run",
            processing_status="done",
        )
        db_session.add(activity)
        await db_session.flush()
        return athlete, activity

    return asyncio.run(_seed())


def test_post_feedback_happy_path(client: TestClient, db_session: AsyncSession) -> None:
    _seed_athlete_and_activity(db_session)
    resp = client.post(
        "/feedback",
        json={"activity_id": 42, "athlete_id": 1, "thumb": "up", "comment": "Spot on."},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["thumb"] == "up"
    assert body["comment"] == "Spot on."
    assert "created_at" in body and "id" in body

    rows = asyncio.run(
        db_session.execute(select(UserFeedback).where(UserFeedback.activity_id == 42))
    ).scalars().all()
    assert len(rows) == 1


def test_post_feedback_invalid_thumb_returns_422(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    resp = client.post(
        "/feedback",
        json={"activity_id": 42, "athlete_id": 1, "thumb": "yes"},
    )
    assert resp.status_code == 422


def test_post_feedback_comment_too_long_returns_422(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    resp = client.post(
        "/feedback",
        json={
            "activity_id": 42,
            "athlete_id": 1,
            "thumb": "up",
            "comment": "x" * 2001,
        },
    )
    assert resp.status_code == 422


def test_post_feedback_activity_does_not_belong_to_athlete_returns_404(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    async def _add_other_athlete() -> None:
        db_session.add(Athlete(id=2, strava_athlete_id=1002))
        await db_session.flush()
    asyncio.run(_add_other_athlete())
    resp = client.post(
        "/feedback",
        json={"activity_id": 42, "athlete_id": 2, "thumb": "up"},
    )
    assert resp.status_code == 404


def test_post_feedback_nonexistent_activity_returns_404(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    resp = client.post(
        "/feedback",
        json={"activity_id": 9999, "athlete_id": 1, "thumb": "up"},
    )
    assert resp.status_code == 404


def test_post_feedback_nonexistent_athlete_returns_404(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    resp = client.post(
        "/feedback",
        json={"activity_id": 42, "athlete_id": 9999, "thumb": "up"},
    )
    assert resp.status_code == 404


def test_post_feedback_two_submits_insert_two_rows(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    for comment in ["first", "second"]:
        resp = client.post(
            "/feedback",
            json={"activity_id": 42, "athlete_id": 1, "thumb": "up", "comment": comment},
        )
        assert resp.status_code == 201
    rows = asyncio.run(
        db_session.execute(select(UserFeedback).where(UserFeedback.activity_id == 42))
    ).scalars().all()
    assert len(rows) == 2


def test_get_feedback_activity_no_existing_returns_null(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    resp = client.get("/feedback/activity/42?athlete_id=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["existing"] is None
    assert body["strava_activity_id"] == 9876543210


def test_get_feedback_activity_returns_most_recent(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_athlete_and_activity(db_session)
    client.post("/feedback", json={"activity_id": 42, "athlete_id": 1, "thumb": "up", "comment": "old"})
    client.post("/feedback", json={"activity_id": 42, "athlete_id": 1, "thumb": "down", "comment": "new"})
    resp = client.get("/feedback/activity/42?athlete_id=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["existing"]["thumb"] == "down"
    assert body["existing"]["comment"] == "new"
