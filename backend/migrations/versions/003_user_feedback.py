"""user_feedback table (thumb + comment from runner, read_at for admin triage).

Revision ID: 003_user_feedback
Revises: 002_admin_dashboard
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "003_user_feedback"
down_revision: Union[str, None] = "002_admin_dashboard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_feedback (
            id SERIAL PRIMARY KEY,
            activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
            athlete_id INTEGER NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
            thumb TEXT NOT NULL CHECK (thumb IN ('up', 'down')),
            comment TEXT,
            read_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_feedback_created ON user_feedback (created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_feedback_activity ON user_feedback (activity_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_feedback_unread ON user_feedback (read_at) "
        "WHERE read_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_feedback_unread")
    op.execute("DROP INDEX IF EXISTS ix_user_feedback_activity")
    op.execute("DROP INDEX IF EXISTS ix_user_feedback_created")
    op.execute("DROP TABLE IF EXISTS user_feedback")
