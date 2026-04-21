import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.routers import auth


FAKE_TOKEN_PAYLOAD = {
    "access_token": "at-123",
    "refresh_token": "rt-123",
    "expires_at": int(datetime.now(timezone.utc).timestamp()) + 3600,
    "athlete": {
        "id": 777,
        "firstname": "Duncan",
        "lastname": "Tester",
        "profile": "https://example.com/avatar.png",
        "city": "Hanoi",
        "country": "Vietnam",
    },
}


def _seed_state(state: str = "test-state") -> str:
    auth._state_store.add(state)
    return state


def test_oauth_callback_fresh_athlete_triggers_backfill(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First-time OAuth connect (no existing athlete) must enqueue exactly
    one backfill."""
    state = _seed_state("state-fresh")

    calls: list[int] = []

    async def fake_enqueue_backfill(athlete_id: int) -> None:
        calls.append(athlete_id)

    monkeypatch.setattr("app.routers.auth.enqueue_backfill", fake_enqueue_backfill)

    async def fake_exchange(code: str) -> dict:
        assert code == "auth-code"
        return FAKE_TOKEN_PAYLOAD

    monkeypatch.setattr("app.routers.auth.exchange_code", fake_exchange)

    response = client.get(
        f"/auth/callback?code=auth-code&state={state}", follow_redirects=False
    )
    assert response.status_code == 302

    # The new athlete should exist in DB with backfilled_at still None
    # (the worker is what sets it — not the callback).
    async def _fetch() -> Athlete:
        result = await db_session.execute(
            select(Athlete).where(Athlete.strava_athlete_id == 777)
        )
        return result.scalar_one()

    athlete = asyncio.run(_fetch())
    assert athlete.backfilled_at is None

    assert calls == [athlete.id], (
        "fresh OAuth connect must schedule exactly one backfill for the new athlete"
    )


def test_oauth_callback_returning_athlete_skips_backfill(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reconnecting an athlete whose backfilled_at is set must NOT fire
    a second backfill."""
    state = _seed_state("state-returning")

    # Pre-create the athlete with backfilled_at populated
    existing = Athlete(
        strava_athlete_id=777,
        backfilled_at=datetime.now(timezone.utc),
    )
    db_session.add(existing)
    asyncio.run(db_session.commit())
    asyncio.run(db_session.refresh(existing))

    calls: list[int] = []

    async def fake_enqueue_backfill(athlete_id: int) -> None:
        calls.append(athlete_id)

    monkeypatch.setattr("app.routers.auth.enqueue_backfill", fake_enqueue_backfill)

    async def fake_exchange(code: str) -> dict:
        return FAKE_TOKEN_PAYLOAD

    monkeypatch.setattr("app.routers.auth.exchange_code", fake_exchange)

    response = client.get(
        f"/auth/callback?code=auth-code&state={state}", follow_redirects=False
    )
    assert response.status_code == 302
    assert calls == [], "already-backfilled athlete must not trigger a backfill"


def test_oauth_callback_existing_athlete_without_backfill_retries(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reconnecting an athlete whose prior backfill failed (backfilled_at
    still None) must retry the backfill."""
    state = _seed_state("state-retry")

    existing = Athlete(
        strava_athlete_id=777,
        backfilled_at=None,
    )
    db_session.add(existing)
    asyncio.run(db_session.commit())
    asyncio.run(db_session.refresh(existing))

    calls: list[int] = []

    async def fake_enqueue_backfill(athlete_id: int) -> None:
        calls.append(athlete_id)

    monkeypatch.setattr("app.routers.auth.enqueue_backfill", fake_enqueue_backfill)

    async def fake_exchange(code: str) -> dict:
        return FAKE_TOKEN_PAYLOAD

    monkeypatch.setattr("app.routers.auth.exchange_code", fake_exchange)

    response = client.get(
        f"/auth/callback?code=auth-code&state={state}", follow_redirects=False
    )
    assert response.status_code == 302
    assert calls == [existing.id], (
        "athlete with null backfilled_at must retry on reconnect"
    )
