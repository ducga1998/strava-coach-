"""Add activities.description_pushed_hash to break push→webhook→push loop.

Without this column we re-push the same description on every webhook
update event that Strava fires in response to our own PUT — which ran
our daily read quota into the ground in a single day.

Revision ID: 004_activity_description_pushed_hash
Revises: 003_user_feedback
Create Date: 2026-04-21

"""
from typing import Sequence, Union

from alembic import op


revision: str = "004_activity_description_pushed_hash"
down_revision: Union[str, None] = "003_user_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE activities ADD COLUMN IF NOT EXISTS description_pushed_hash VARCHAR(64)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE activities DROP COLUMN IF EXISTS description_pushed_hash")
