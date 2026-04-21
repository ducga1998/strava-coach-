from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.credentials import StravaCredential
from app.services.activity_ingestion import backfill_recent_activities


@pytest_asyncio.fixture
async def athlete_with_credential(db_session: AsyncSession) -> Athlete:
    athlete = Athlete(strava_athlete_id=42)
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)

    # The real encryption may want bytes; since we mock token_service.decrypt,
    # the exact on-disk byte shape never matters. If the StravaCredential
    # model rejects bytes here, fall back to str values — the mock short-
    # circuits before decryption is attempted.
    credential = StravaCredential(
        athlete_id=athlete.id,
        access_token_enc=b"fake-access-enc",
        refresh_token_enc=b"fake-refresh-enc",
        expires_at=int(datetime.now(timezone.utc).timestamp()) + 3600,
    )
    db_session.add(credential)
    await db_session.commit()
    return athlete


@pytest.mark.asyncio
async def test_backfill_marks_backfilled_at_on_success(
    db_session: AsyncSession, athlete_with_credential: Athlete
):
    """After a successful backfill (even with zero activities ingested),
    athlete.backfilled_at must be set to a UTC-aware datetime."""
    client = AsyncMock()
    client.get_athlete_activities.return_value = []

    # token_service.decrypt is synchronous in the real service; MagicMock
    # gives us a sync return, matching production behavior.
    token_service = MagicMock()
    token_service.decrypt = MagicMock(return_value="fake-token")

    before = datetime.now(timezone.utc)

    count = await backfill_recent_activities(
        session=db_session,
        athlete_id=athlete_with_credential.id,
        client=client,
        token_service=token_service,
        limit=10,
    )
    assert count == 0  # empty summaries

    await db_session.refresh(athlete_with_credential)
    assert athlete_with_credential.backfilled_at is not None
    # SQLite in tests may strip tzinfo; re-attach UTC if missing, matching
    # the pattern used in test_plan_import_sync.py.
    stamped = athlete_with_credential.backfilled_at
    if stamped.tzinfo is None:
        stamped = stamped.replace(tzinfo=timezone.utc)
    assert stamped >= before


@pytest.mark.asyncio
async def test_backfill_does_not_mark_when_list_summaries_raises(
    db_session: AsyncSession, athlete_with_credential: Athlete
):
    """If the list-summaries call fails, backfilled_at must stay None so
    the next OAuth reconnect will retry."""
    client = AsyncMock()
    client.get_athlete_activities.side_effect = RuntimeError("429 rate limited")

    token_service = MagicMock()
    token_service.decrypt = MagicMock(return_value="fake-token")

    with pytest.raises(RuntimeError, match="429"):
        await backfill_recent_activities(
            session=db_session,
            athlete_id=athlete_with_credential.id,
            client=client,
            token_service=token_service,
            limit=10,
        )

    await db_session.refresh(athlete_with_credential)
    assert athlete_with_credential.backfilled_at is None


@pytest.mark.asyncio
async def test_backfill_no_credential_does_not_mark(
    db_session: AsyncSession
):
    """An athlete with no credential returns early with count=0; backfilled_at
    must stay None (we didn't actually fetch anything)."""
    athlete = Athlete(strava_athlete_id=99)
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)

    client = AsyncMock()
    token_service = MagicMock()
    token_service.decrypt = MagicMock(return_value="fake-token")

    count = await backfill_recent_activities(
        session=db_session,
        athlete_id=athlete.id,
        client=client,
        token_service=token_service,
    )
    assert count == 0

    await db_session.refresh(athlete)
    assert athlete.backfilled_at is None
