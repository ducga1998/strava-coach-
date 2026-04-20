import asyncio
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import cli as admin_cli
from app.admin.models import Admin


@pytest.mark.asyncio
async def test_create_admin_command_prints_password(
    db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    class _Ctx:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *a):
            # Don't close — fixture owns the session.
            pass

    def fake_open_session():
        return _Ctx()

    with patch.object(admin_cli, "_open_session", fake_open_session):
        await admin_cli.run(["create-admin", "--email", "a@example.com", "--name", "Alice"])

    captured = capsys.readouterr()
    assert "a@example.com" in captured.out
    assert "Generated password:" in captured.out

    row = (await db_session.execute(select(Admin))).scalar_one()
    assert row.email == "a@example.com"
    assert row.name == "Alice"
