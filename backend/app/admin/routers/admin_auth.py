from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import auth as admin_auth
from app.admin.models import Admin, AdminSession
from app.admin.schemas import ChangePasswordRequest, LoginRequest, MeResponse
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

# Computed once at import time. Used to make the "admin not found / disabled"
# path run argon2 verify so response latency matches the happy path. The
# dummy password is never accepted — it's only used to equalise timing.
_DUMMY_PASSWORD_HASH = admin_auth.hash_password("timing-attack-defence-placeholder")


def _cookie_kwargs() -> dict:
    # In tests (starlette TestClient) SameSite/Secure don't interfere with
    # cookie round-trips; in prod we want HttpOnly + Secure + SameSite=Lax.
    return {
        "httponly": True,
        "secure": not settings.frontend_url.startswith("http://localhost"),
        "samesite": "lax",
        "path": "/admin",
    }


@router.post("/login", response_model=MeResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    normalised = payload.email.lower()
    admin = (
        await db.execute(select(Admin).where(Admin.email == normalised))
    ).scalar_one_or_none()
    if admin is None or admin.disabled_at is not None:
        # Run argon2 verify against a dummy hash to keep response time
        # constant whether the admin exists or not.
        admin_auth.verify_password(_DUMMY_PASSWORD_HASH, payload.password)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not admin_auth.verify_password(admin.password_hash, payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    raw_token = await admin_auth.create_session(
        db,
        admin,
        lifetime_days=settings.admin_session_lifetime_days,
        user_agent=request.headers.get("user-agent"),
    )
    admin.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    response.set_cookie(
        key=admin_auth.SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=settings.admin_session_lifetime_days * 24 * 3600,
        **_cookie_kwargs(),
    )
    return MeResponse(id=admin.id, email=admin.email, name=admin.name)


@router.get("/me", response_model=MeResponse)
async def me(admin: Admin = Depends(admin_auth.require_admin)) -> MeResponse:
    return MeResponse(id=admin.id, email=admin.email, name=admin.name)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Response:
    raw = request.cookies.get(admin_auth.SESSION_COOKIE_NAME)
    if raw:
        await admin_auth.revoke_session(db, raw)
        await db.commit()
    response.delete_cookie(admin_auth.SESSION_COOKIE_NAME, path="/admin")
    response.status_code = 204
    return response


@router.post("/change-password", status_code=204)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    admin: Admin = Depends(admin_auth.require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if not admin_auth.verify_password(admin.password_hash, payload.current):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    admin.password_hash = admin_auth.hash_password(payload.new)

    # Revoke ALL sessions for this admin (including current), then mint a
    # fresh one so the caller stays logged in.
    await db.execute(
        update(AdminSession)
        .where(
            AdminSession.admin_id == admin.id,
            AdminSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    new_raw = await admin_auth.create_session(
        db,
        admin,
        lifetime_days=settings.admin_session_lifetime_days,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    response.set_cookie(
        key=admin_auth.SESSION_COOKIE_NAME,
        value=new_raw,
        max_age=settings.admin_session_lifetime_days * 24 * 3600,
        **_cookie_kwargs(),
    )
    response.status_code = 204
    return response
