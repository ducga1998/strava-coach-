import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.credentials import StravaCredential
from app.routers import webhook


def test_webhook_challenge(client: TestClient) -> None:
    response = client.get(
        "/webhook/strava",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "abc123",
            "hub.verify_token": settings.strava_verify_token,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"hub.challenge": "abc123"}


def test_webhook_bad_verify_token(client: TestClient) -> None:
    response = client.get(
        "/webhook/strava",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "abc123",
            "hub.verify_token": "wrong",
        },
    )
    assert response.status_code == 403


def test_webhook_bad_mode(client: TestClient) -> None:
    response = client.get(
        "/webhook/strava",
        params={
            "hub.mode": "unsubscribe",
            "hub.challenge": "abc123",
            "hub.verify_token": settings.strava_verify_token,
        },
    )
    assert response.status_code == 403


def test_webhook_create_event_enqueues_activity(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[int, int]] = []

    async def fake_enqueue_activity(strava_athlete_id: int, strava_activity_id: int) -> None:
        calls.append((strava_athlete_id, strava_activity_id))

    monkeypatch.setattr(webhook, "enqueue_activity", fake_enqueue_activity)
    response = client.post("/webhook/strava", json=_event("activity", "create"))
    assert response.status_code == 200
    assert calls == [(1001, 2002)]


def test_webhook_update_event_enqueues_activity(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[int, int]] = []

    async def fake_enqueue_activity(strava_athlete_id: int, strava_activity_id: int) -> None:
        calls.append((strava_athlete_id, strava_activity_id))

    monkeypatch.setattr(webhook, "enqueue_activity", fake_enqueue_activity)
    response = client.post(
        "/webhook/strava",
        json=_event("activity", "update", updates={"title": "New title"}),
    )
    assert response.status_code == 200
    assert calls == [(1001, 2002)]


def test_webhook_delete_event_deletes_activity(
    client: TestClient, db_session: AsyncSession
) -> None:
    db_session.add(Athlete(id=1, strava_athlete_id=1001))
    db_session.add(Activity(id=1, athlete_id=1, strava_activity_id=2002))
    asyncio.run(db_session.commit())

    response = client.post("/webhook/strava", json=_event("activity", "delete"))

    activity = asyncio.run(db_session.scalar(select(Activity).where(Activity.id == 1)))
    assert response.status_code == 200
    assert activity is None


def test_webhook_deauthorization_flags_credentials(
    client: TestClient, db_session: AsyncSession
) -> None:
    db_session.add(Athlete(id=1, strava_athlete_id=1001))
    db_session.add(
        StravaCredential(
            athlete_id=1,
            access_token_enc="access",
            refresh_token_enc="refresh",
            expires_at=123,
            source_disconnected=False,
        )
    )
    asyncio.run(db_session.commit())

    response = client.post(
        "/webhook/strava",
        json=_event("athlete", "update", object_id=1001, updates={"authorized": "false"}),
    )

    credential = asyncio.run(db_session.scalar(select(StravaCredential)))
    assert response.status_code == 200
    assert credential is not None
    assert credential.source_disconnected is True


def test_webhook_deauthorization_flags_credentials_boolean(
    client: TestClient, db_session: AsyncSession
) -> None:
    db_session.add(Athlete(id=2, strava_athlete_id=1002))
    db_session.add(
        StravaCredential(
            athlete_id=2,
            access_token_enc="access",
            refresh_token_enc="refresh",
            expires_at=123,
            source_disconnected=False,
        )
    )
    asyncio.run(db_session.commit())

    response = client.post(
        "/webhook/strava",
        json=_event("athlete", "update", object_id=1002, updates={"authorized": False}),
    )

    credential = asyncio.run(
        db_session.scalar(select(StravaCredential).where(StravaCredential.athlete_id == 2))
    )
    assert response.status_code == 200
    assert credential is not None
    assert credential.source_disconnected is True


from typing import Any

def _event(
    object_type: str,
    aspect_type: str,
    *,
    object_id: int = 2002,
    updates: dict[str, Any] | None = None,
) -> dict[str, object]:
    return {
        "object_type": object_type,
        "object_id": object_id,
        "aspect_type": aspect_type,
        "owner_id": 1001,
        "subscription_id": 99,
        "event_time": 1549560669,
        "updates": updates or {},
    }
