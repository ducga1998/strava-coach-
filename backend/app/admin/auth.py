import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import Admin, AdminSession
from app.database import get_db

_hasher = PasswordHasher()

SESSION_COOKIE_NAME = "admin_session"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        _hasher.verify(hashed, password)
        return True
    except VerificationError:
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def create_session(
    db: AsyncSession,
    admin: Admin,
    lifetime_days: int,
    user_agent: str | None = None,
) -> str:
    """Create a new admin session row. FLUSHES but does not COMMIT — the
    caller is responsible for the surrounding transaction. Returns the raw
    session token; store only the sha256 (already persisted here)."""
    raw = generate_session_token()
    session = AdminSession(
        admin_id=admin.id,
        token_hash=hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=lifetime_days),
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(session)
    await db.flush()
    return raw


async def lookup_admin_by_session(db: AsyncSession, raw_token: str) -> Admin | None:
    row = (
        await db.execute(
            select(AdminSession).where(AdminSession.token_hash == hash_token(raw_token))
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.revoked_at is not None:
        return None
    if row.expires_at <= datetime.now(timezone.utc):
        return None
    admin = await db.get(Admin, row.admin_id)
    if admin is None or admin.disabled_at is not None:
        return None
    return admin


async def revoke_session(db: AsyncSession, raw_token: str) -> None:
    """Mark the session revoked. FLUSHES but does not COMMIT — caller owns
    the transaction."""
    row = (
        await db.execute(
            select(AdminSession).where(AdminSession.token_hash == hash_token(raw_token))
        )
    ).scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        await db.flush()


async def require_admin(
    request: Request,
    admin_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> Admin:
    if not admin_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    admin = await lookup_admin_by_session(db, admin_session)
    if admin is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return admin
