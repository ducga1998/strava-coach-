"""Add athlete columns used by Strava OAuth (avatar, city, country).

Revision ID: 001_athlete_profile
Revises:
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op

revision: str = "001_athlete_profile"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS keeps this safe for DBs that already have some columns (PostgreSQL 11+).
    op.execute(
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500)"
    )
    op.execute("ALTER TABLE athletes ADD COLUMN IF NOT EXISTS city VARCHAR(100)")
    op.execute("ALTER TABLE athletes ADD COLUMN IF NOT EXISTS country VARCHAR(100)")


def downgrade() -> None:
    op.execute("ALTER TABLE athletes DROP COLUMN IF EXISTS avatar_url")
    op.execute("ALTER TABLE athletes DROP COLUMN IF EXISTS city")
    op.execute("ALTER TABLE athletes DROP COLUMN IF EXISTS country")
