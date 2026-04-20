import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import auth as admin_auth
from app.admin.models import Admin
from app.admin.services.admin_invite import create_admin, AdminAlreadyExists


@pytest.mark.asyncio
async def test_create_admin_returns_generated_password(db_session: AsyncSession) -> None:
    result = await create_admin(db_session, email="a@example.com", name="Alice")
    assert result.email == "a@example.com"
    assert len(result.generated_password) >= 16
    # Stored hash verifies against the generated password
    row = (await db_session.execute(select(Admin))).scalar_one()
    assert admin_auth.verify_password(row.password_hash, result.generated_password)
    assert row.name == "Alice"


@pytest.mark.asyncio
async def test_create_admin_lowercases_email(db_session: AsyncSession) -> None:
    await create_admin(db_session, email="Alice@Example.COM", name=None)
    row = (await db_session.execute(select(Admin))).scalar_one()
    assert row.email == "alice@example.com"


@pytest.mark.asyncio
async def test_create_admin_rejects_duplicate(db_session: AsyncSession) -> None:
    await create_admin(db_session, email="a@example.com", name=None)
    with pytest.raises(AdminAlreadyExists):
        await create_admin(db_session, email="a@example.com", name=None)
