"""Training plan entries + athlete sheet URL settings.

Revision ID: 005_training_plan
Revises: 004_activity_desc_hash
Create Date: 2026-04-21

"""
from typing import Sequence, Union

from alembic import op


revision: str = "005_training_plan"
down_revision: Union[str, None] = "004_activity_desc_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


WORKOUT_TYPES = (
    "recovery", "easy", "long", "tempo", "interval",
    "hill", "race", "rest", "cross", "strength",
)


def upgrade() -> None:
    types_list = ", ".join(f"'{t}'" for t in WORKOUT_TYPES)
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS training_plan_entries (
            id SERIAL PRIMARY KEY,
            athlete_id INTEGER NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            workout_type TEXT NOT NULL CHECK (workout_type IN ({types_list})),
            planned_tss REAL,
            planned_duration_min INTEGER,
            planned_distance_km REAL,
            planned_elevation_m INTEGER,
            description TEXT,
            source TEXT NOT NULL DEFAULT 'sheet_csv',
            imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (athlete_id, date)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_training_plan_athlete_date "
        "ON training_plan_entries (athlete_id, date)"
    )
    op.execute(
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS plan_sheet_url TEXT"
    )
    op.execute(
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS plan_synced_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE athletes DROP COLUMN IF EXISTS plan_synced_at")
    op.execute("ALTER TABLE athletes DROP COLUMN IF EXISTS plan_sheet_url")
    op.execute("DROP INDEX IF EXISTS ix_training_plan_athlete_date")
    op.execute("DROP TABLE IF EXISTS training_plan_entries")
