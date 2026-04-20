import argparse
import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.services.admin_invite import AdminAlreadyExists, create_admin
from app.database import SessionLocal


@asynccontextmanager
async def _open_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def _cmd_create_admin(email: str, name: str | None) -> int:
    async with _open_session() as db:
        try:
            result = await create_admin(db, email=email, name=name)
            await db.commit()
        except AdminAlreadyExists:
            print(f"error: admin '{email}' already exists", file=sys.stderr)
            return 1
    print(f"Created admin: {result.email}")
    print(f"Generated password: {result.generated_password}")
    print("Share out of band. Admin should log in and change it immediately.")
    return 0


async def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.admin.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p_create = sub.add_parser("create-admin", help="Create a new admin account")
    p_create.add_argument("--email", required=True)
    p_create.add_argument("--name", default=None)

    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return await _cmd_create_admin(email=args.email, name=args.name)
    return 2


def main() -> None:  # pragma: no cover
    sys.exit(asyncio.run(run(sys.argv[1:])))


if __name__ == "__main__":  # pragma: no cover
    main()
