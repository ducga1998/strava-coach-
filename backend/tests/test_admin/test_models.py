import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.admin.models import (
    Admin,
    AdminSession,
    PromptVersion,
    DebriefRun,
    DebriefRating,
    DebriefAutoFlag,
    Thumb,
)
from app.models.athlete import Athlete


@pytest.mark.asyncio
async def test_admin_tables_created(db_session: AsyncSession) -> None:
    """All admin tables should be creatable via Base.metadata.create_all."""
    result = await db_session.execute(select(Admin))
    assert result.all() == []
    result = await db_session.execute(select(AdminSession))
    assert result.all() == []
    result = await db_session.execute(select(PromptVersion))
    assert result.all() == []
    result = await db_session.execute(select(DebriefRun))
    assert result.all() == []
    result = await db_session.execute(select(DebriefRating))
    assert result.all() == []
    result = await db_session.execute(select(DebriefAutoFlag))
    assert result.all() == []


@pytest.mark.asyncio
async def test_athlete_has_disabled_at(db_session: AsyncSession) -> None:
    athlete = Athlete(strava_athlete_id=42, firstname="Test")
    db_session.add(athlete)
    await db_session.flush()
    assert athlete.disabled_at is None


def test_thumb_enum_values() -> None:
    assert Thumb.up.value == "up"
    assert Thumb.down.value == "down"
