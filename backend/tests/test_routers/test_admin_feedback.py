import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import auth as admin_auth
from app.admin.models import Admin
from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.feedback import UserFeedback


def _seed_world(db_session: AsyncSession) -> None:
    async def _seed() -> None:
        db_session.add(Admin(
            id=1, email="admin@example.com",
            password_hash=admin_auth.hash_password("pw"), name="Admin",
        ))
        db_session.add(Athlete(id=10, strava_athlete_id=1001))
        db_session.add(Athlete(id=11, strava_athlete_id=1002))
        await db_session.flush()
        db_session.add(Activity(
            id=100, athlete_id=10, strava_activity_id=9_000_000_001,
            name="Morning Run", sport_type="Run", processing_status="done",
        ))
        db_session.add(Activity(
            id=101, athlete_id=11, strava_activity_id=9_000_000_002,
            name="Trail 22k", sport_type="TrailRun", processing_status="done",
        ))
        await db_session.flush()
        db_session.add_all([
            UserFeedback(id=1, activity_id=100, athlete_id=10, thumb="down", comment="Not actionable."),
            UserFeedback(id=2, activity_id=101, athlete_id=11, thumb="up"),
            UserFeedback(id=3, activity_id=100, athlete_id=10, thumb="up", comment="Better."),
        ])
        await db_session.flush()
    asyncio.run(_seed())


def _login(client: TestClient) -> None:
    resp = client.post(
        "/admin/auth/login",
        json={"email": "admin@example.com", "password": "pw"},
    )
    assert resp.status_code == 200


def test_admin_feedback_requires_auth(client: TestClient, db_session: AsyncSession) -> None:
    _seed_world(db_session)
    resp = client.get("/admin/feedback")
    assert resp.status_code == 401


def test_admin_feedback_list_all(client: TestClient, db_session: AsyncSession) -> None:
    _seed_world(db_session)
    _login(client)
    resp = client.get("/admin/feedback")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3
    assert [i["id"] for i in body["items"]] == [3, 2, 1]
    assert body["next_cursor"] is None
    first = body["items"][0]
    assert first["activity_name"] == "Morning Run"
    assert first["athlete_id"] == 10


def test_admin_feedback_filter_down(client: TestClient, db_session: AsyncSession) -> None:
    _seed_world(db_session)
    _login(client)
    resp = client.get("/admin/feedback?thumb=down")
    assert resp.status_code == 200
    body = resp.json()
    assert [i["id"] for i in body["items"]] == [1]


def test_admin_feedback_filter_unread(client: TestClient, db_session: AsyncSession) -> None:
    _seed_world(db_session)
    _login(client)
    resp = client.get("/admin/feedback?unread=true")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 3


def test_admin_feedback_cursor_pagination(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_world(db_session)
    async def _more() -> None:
        for i in range(4, 25):
            db_session.add(UserFeedback(
                id=i, activity_id=100, athlete_id=10, thumb="up",
            ))
        await db_session.flush()
    asyncio.run(_more())
    _login(client)
    page1 = client.get("/admin/feedback").json()
    assert len(page1["items"]) == 20
    assert page1["next_cursor"] is not None
    page2 = client.get(f"/admin/feedback?cursor={page1['next_cursor']}").json()
    assert len(page2["items"]) == 4
    assert page2["next_cursor"] is None


def test_admin_feedback_counts(client: TestClient, db_session: AsyncSession) -> None:
    _seed_world(db_session)
    _login(client)
    resp = client.get("/admin/feedback/counts")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"all": 3, "up": 2, "down": 1, "unread": 3}


def test_admin_feedback_mark_read(client: TestClient, db_session: AsyncSession) -> None:
    _seed_world(db_session)
    _login(client)
    resp = client.patch("/admin/feedback/1/read")
    assert resp.status_code == 204
    resp2 = client.patch("/admin/feedback/1/read")
    assert resp2.status_code == 204
    counts = client.get("/admin/feedback/counts").json()
    assert counts["unread"] == 2
