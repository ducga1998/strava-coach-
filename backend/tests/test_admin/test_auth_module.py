from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import auth as admin_auth
from app.admin.models import Admin, AdminSession


def test_hash_password_returns_argon2id_string() -> None:
    h = admin_auth.hash_password("correcthorsebatterystaple")
    assert h.startswith("$argon2id$")


def test_verify_password_correct() -> None:
    h = admin_auth.hash_password("correcthorsebatterystaple")
    assert admin_auth.verify_password(h, "correcthorsebatterystaple") is True


def test_verify_password_wrong() -> None:
    h = admin_auth.hash_password("correcthorsebatterystaple")
    assert admin_auth.verify_password(h, "wrong") is False


def test_generate_session_token_is_urlsafe_and_unique() -> None:
    a = admin_auth.generate_session_token()
    b = admin_auth.generate_session_token()
    assert a != b
    assert len(a) >= 32
    assert all(c.isalnum() or c in "-_" for c in a)


def test_hash_token_is_deterministic_hex_sha256() -> None:
    t = "some-session-token"
    assert admin_auth.hash_token(t) == admin_auth.hash_token(t)
    assert len(admin_auth.hash_token(t)) == 64


@pytest.mark.asyncio
async def test_create_session_stores_hashed_token(db_session: AsyncSession) -> None:
    admin = Admin(email="a@example.com", password_hash=admin_auth.hash_password("x" * 12))
    db_session.add(admin)
    await db_session.flush()

    raw_token = await admin_auth.create_session(db_session, admin, lifetime_days=14)

    row = (await db_session.execute(select(AdminSession))).scalar_one()
    assert row.token_hash == admin_auth.hash_token(raw_token)
    assert row.token_hash != raw_token
    assert row.revoked_at is None
    assert row.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_lookup_session_returns_admin(db_session: AsyncSession) -> None:
    admin = Admin(email="a@example.com", password_hash=admin_auth.hash_password("x" * 12))
    db_session.add(admin)
    await db_session.flush()

    raw_token = await admin_auth.create_session(db_session, admin, lifetime_days=14)
    found = await admin_auth.lookup_admin_by_session(db_session, raw_token)
    assert found is not None
    assert found.id == admin.id


@pytest.mark.asyncio
async def test_lookup_session_rejects_expired(db_session: AsyncSession) -> None:
    admin = Admin(email="a@example.com", password_hash=admin_auth.hash_password("x" * 12))
    db_session.add(admin)
    await db_session.flush()
    raw_token = admin_auth.generate_session_token()
    expired = AdminSession(
        admin_id=admin.id,
        token_hash=admin_auth.hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(expired)
    await db_session.flush()

    found = await admin_auth.lookup_admin_by_session(db_session, raw_token)
    assert found is None


@pytest.mark.asyncio
async def test_lookup_session_rejects_revoked(db_session: AsyncSession) -> None:
    admin = Admin(email="a@example.com", password_hash=admin_auth.hash_password("x" * 12))
    db_session.add(admin)
    await db_session.flush()
    raw_token = await admin_auth.create_session(db_session, admin, lifetime_days=14)
    session = (await db_session.execute(select(AdminSession))).scalar_one()
    session.revoked_at = datetime.now(timezone.utc)
    await db_session.flush()

    found = await admin_auth.lookup_admin_by_session(db_session, raw_token)
    assert found is None


@pytest.mark.asyncio
async def test_lookup_session_rejects_disabled_admin(db_session: AsyncSession) -> None:
    admin = Admin(
        email="a@example.com",
        password_hash=admin_auth.hash_password("x" * 12),
        disabled_at=datetime.now(timezone.utc),
    )
    db_session.add(admin)
    await db_session.flush()
    raw_token = await admin_auth.create_session(db_session, admin, lifetime_days=14)

    found = await admin_auth.lookup_admin_by_session(db_session, raw_token)
    assert found is None


@pytest.mark.asyncio
async def test_revoke_session(db_session: AsyncSession) -> None:
    admin = Admin(email="a@example.com", password_hash=admin_auth.hash_password("x" * 12))
    db_session.add(admin)
    await db_session.flush()
    raw_token = await admin_auth.create_session(db_session, admin, lifetime_days=14)

    await admin_auth.revoke_session(db_session, raw_token)
    row = (await db_session.execute(select(AdminSession))).scalar_one()
    assert row.revoked_at is not None
