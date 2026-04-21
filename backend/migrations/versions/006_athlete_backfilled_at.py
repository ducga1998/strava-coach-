"""Add athletes.backfilled_at to gate one-time history backfill.

Set once by the backfill worker after successful completion; checked by
the OAuth callback to decide whether to enqueue a backfill. Null means
"never backfilled"; any non-null datetime means "skip".

Revision ID: 006_athlete_backfilled_at
Revises: 005_training_plan
Create Date: 2026-04-21

"""
from typing import Sequence, Union

from alembic import op


revision: str = "006_athlete_backfilled_at"
down_revision: Union[str, None] = "005_training_plan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS backfilled_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE athletes DROP COLUMN IF EXISTS backfilled_at")
