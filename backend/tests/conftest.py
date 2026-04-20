import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import TypeAlias

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
import app.admin.models  # noqa: F401
from app.database import Base, get_db
from app.main import app
from app.services import webhook_subscription as _ws


@pytest.fixture(autouse=True)
def _skip_strava_webhook_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tests that boot the FastAPI app must not call Strava on startup.

    Without this, every TestClient(app) triggers ensure_webhook_subscription
    → hits the real API → 429 retry loop → tests run for minutes.
    """

    async def _fake_ensure() -> _ws.SubscriptionStatus:
        return _ws.SubscriptionStatus(state="skipped", reason="test harness")

    monkeypatch.setattr("app.main.ensure_webhook_subscription", _fake_ensure)

SessionMaker: TypeAlias = async_sessionmaker[AsyncSession]


@pytest.fixture
def db_session() -> Generator[AsyncSession, None, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    session = asyncio.run(create_session(engine, maker))
    yield session
    asyncio.run(session.close())
    asyncio.run(engine.dispose())


@pytest.fixture
def client(db_session: AsyncSession) -> Generator[TestClient, None, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as api:
        yield api
    app.dependency_overrides.clear()


async def create_session(engine: AsyncEngine, maker: SessionMaker) -> AsyncSession:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return maker()
