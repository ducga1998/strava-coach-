"""Add athletes.disabled_at for admin disable/enable flow.

Revision ID: 002_athletes_disabled_at
Revises: 001_athlete_profile
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "002_athletes_disabled_at"
down_revision: Union[str, None] = "001_athlete_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS disabled_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE athletes DROP COLUMN IF EXISTS disabled_at")
