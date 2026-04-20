import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import auth as admin_auth
from app.admin.models import Admin


class AdminAlreadyExists(Exception):
    pass


@dataclass
class CreatedAdmin:
    email: str
    name: str | None
    generated_password: str


async def create_admin(
    db: AsyncSession,
    email: str,
    name: str | None,
) -> CreatedAdmin:
    normalised = email.strip().lower()
    existing = (
        await db.execute(select(Admin).where(Admin.email == normalised))
    ).scalar_one_or_none()
    if existing is not None:
        raise AdminAlreadyExists(normalised)
    password = secrets.token_urlsafe(18)
    admin = Admin(
        email=normalised,
        password_hash=admin_auth.hash_password(password),
        name=name,
    )
    db.add(admin)
    await db.flush()
    return CreatedAdmin(email=normalised, name=name, generated_password=password)
