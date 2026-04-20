import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import auth as admin_auth
from app.admin.models import Admin


@pytest.fixture
def seed_admin(db_session: AsyncSession):
    import asyncio
    async def _seed():
        admin = Admin(
            email="alice@example.com",
            password_hash=admin_auth.hash_password("correctpassword"),
            name="Alice",
        )
        db_session.add(admin)
        await db_session.flush()
        return admin

    return asyncio.run(_seed())


def test_login_success(client: TestClient, seed_admin: Admin) -> None:
    response = client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "correctpassword"},
    )
    assert response.status_code == 200
    assert response.cookies.get(admin_auth.SESSION_COOKIE_NAME)
    assert response.json() == {"id": seed_admin.id, "email": "alice@example.com", "name": "Alice"}


def test_login_wrong_password(client: TestClient, seed_admin: Admin) -> None:
    response = client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.cookies.get(admin_auth.SESSION_COOKIE_NAME) is None


def test_login_unknown_email(client: TestClient) -> None:
    response = client.post(
        "/admin/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert response.status_code == 401


def test_login_case_insensitive_email(client: TestClient, seed_admin: Admin) -> None:
    response = client.post(
        "/admin/auth/login",
        json={"email": "ALICE@EXAMPLE.COM", "password": "correctpassword"},
    )
    assert response.status_code == 200


def test_login_disabled_admin_rejected(
    client: TestClient, seed_admin: Admin, db_session: AsyncSession
) -> None:
    import asyncio
    from datetime import datetime, timezone
    from sqlalchemy import select

    async def _disable():
        # Re-fetch in this loop to avoid cross-loop detached-instance issues.
        fresh = (
            await db_session.execute(
                select(Admin).where(Admin.email == "alice@example.com")
            )
        ).scalar_one()
        fresh.disabled_at = datetime.now(timezone.utc)
        await db_session.flush()

    asyncio.run(_disable())
    response = client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "correctpassword"},
    )
    assert response.status_code == 401


def _login(client: TestClient) -> None:
    r = client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "correctpassword"},
    )
    assert r.status_code == 200


def test_me_without_cookie_returns_401(client: TestClient) -> None:
    assert client.get("/admin/auth/me").status_code == 401


def test_me_returns_current_admin(client: TestClient, seed_admin: Admin) -> None:
    _login(client)
    response = client.get("/admin/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_logout_revokes_session(client: TestClient, seed_admin: Admin) -> None:
    _login(client)
    response = client.post("/admin/auth/logout")
    assert response.status_code == 204
    # Subsequent /me should now 401
    assert client.get("/admin/auth/me").status_code == 401


def test_logout_without_cookie_is_noop(client: TestClient) -> None:
    assert client.post("/admin/auth/logout").status_code == 204


def test_change_password_success(client: TestClient, seed_admin: Admin) -> None:
    _login(client)
    response = client.post(
        "/admin/auth/change-password",
        json={"current": "correctpassword", "new": "brand-new-12chars"},
    )
    assert response.status_code == 204
    # Old password no longer works
    client.cookies.clear()
    r = client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "correctpassword"},
    )
    assert r.status_code == 401
    # New password works
    r = client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "brand-new-12chars"},
    )
    assert r.status_code == 200


def test_change_password_rejects_wrong_current(
    client: TestClient, seed_admin: Admin
) -> None:
    _login(client)
    response = client.post(
        "/admin/auth/change-password",
        json={"current": "wrong", "new": "brand-new-12chars"},
    )
    assert response.status_code == 400


def test_change_password_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/admin/auth/change-password",
        json={"current": "x" * 12, "new": "y" * 12},
    )
    assert response.status_code == 401


def test_change_password_rejects_too_short(
    client: TestClient, seed_admin: Admin
) -> None:
    _login(client)
    response = client.post(
        "/admin/auth/change-password",
        json={"current": "correctpassword", "new": "short"},
    )
    assert response.status_code == 422


def test_login_constant_time_on_unknown_email(
    client: TestClient, seed_admin: Admin
) -> None:
    """Unknown-email path also runs verify_password (for timing uniformity)."""
    import time
    # Measure a wrong-password response (admin exists, argon2 runs)
    t0 = time.monotonic()
    client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password-x"},
    )
    dt_wrong_pw = time.monotonic() - t0
    # Measure an unknown-email response
    t0 = time.monotonic()
    client.post(
        "/admin/auth/login",
        json={"email": "nobody@example.com", "password": "wrong-password-x"},
    )
    dt_unknown = time.monotonic() - t0
    # Both should be in the same order of magnitude (argon2 dominates both).
    # We don't assert exact parity — just that the unknown path didn't short-circuit.
    assert dt_unknown > 0.005, (
        f"unknown-email path too fast ({dt_unknown:.3f}s) — "
        "timing-attack mitigation not running"
    )


def test_change_password_revokes_other_sessions(
    client: TestClient, seed_admin: Admin
) -> None:
    """Changing the password must kill existing sessions from other clients."""
    # Session A: the one changing the password
    client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "correctpassword"},
    )

    # Session B: a second TestClient simulating another device
    from fastapi.testclient import TestClient as TC
    from app.main import app
    client_b = TC(app)
    # Share the same DB via dependency_overrides already set
    r = client_b.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "correctpassword"},
    )
    assert r.status_code == 200
    assert client_b.get("/admin/auth/me").status_code == 200  # live

    # Client A changes the password
    r = client.post(
        "/admin/auth/change-password",
        json={"current": "correctpassword", "new": "brand-new-12chars"},
    )
    assert r.status_code == 204

    # Client B's session is now dead
    assert client_b.get("/admin/auth/me").status_code == 401
    # Client A's session is re-issued and still live
    assert client.get("/admin/auth/me").status_code == 200
