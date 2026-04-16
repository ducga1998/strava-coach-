import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import TypeAlias

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models
from app.database import Base, get_db
from app.main import app

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
