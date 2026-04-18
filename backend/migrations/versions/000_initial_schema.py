"""Create all initial tables.

Revision ID: 000_initial_schema
Revises:
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "000_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE IF NOT EXISTS units AS ENUM ('metric', 'imperial')")
    op.execute("CREATE TYPE IF NOT EXISTS priority AS ENUM ('A', 'B', 'C')")

    op.create_table(
        "athletes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("strava_athlete_id", sa.BigInteger(), nullable=False),
        sa.Column("firstname", sa.String(100), nullable=True),
        sa.Column("lastname", sa.String(100), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_athletes_strava_athlete_id", "athletes", ["strava_athlete_id"], unique=True)

    op.create_table(
        "athlete_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("lthr", sa.Integer(), nullable=True),
        sa.Column("max_hr", sa.Integer(), nullable=True),
        sa.Column("threshold_pace_sec_km", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("vo2max_estimate", sa.Float(), nullable=True),
        sa.Column("units", sa.Enum("metric", "imperial", name="units"), nullable=False, server_default="metric"),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("onboarding_complete", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_athlete_profiles_athlete_id", "athlete_profiles", ["athlete_id"], unique=True)

    op.create_table(
        "strava_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("access_token_enc", sa.Text(), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("refresh_failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_disconnected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("webhook_subscription_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_strava_credentials_athlete_id", "strava_credentials", ["athlete_id"], unique=True)

    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("strava_activity_id", sa.BigInteger(), nullable=False),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("sport_type", sa.String(50), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_time_sec", sa.Integer(), nullable=True),
        sa.Column("moving_time_sec", sa.Integer(), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("total_elevation_gain_m", sa.Float(), nullable=True),
        sa.Column("average_heartrate", sa.Float(), nullable=True),
        sa.Column("max_heartrate", sa.Float(), nullable=True),
        sa.Column("streams_raw", sa.JSON(), nullable=True),
        sa.Column("debrief", sa.JSON(), nullable=True),
        sa.Column("excluded_from_load", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("skipped_reason", sa.String(100), nullable=True),
        sa.Column("processing_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_activities_strava_activity_id", "activities", ["strava_activity_id"], unique=True)
    op.create_index("ix_activities_athlete_id", "activities", ["athlete_id"])

    op.create_table(
        "activity_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("activities.id"), nullable=False),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("tss", sa.Float(), nullable=True),
        sa.Column("hr_tss", sa.Float(), nullable=True),
        sa.Column("gap_avg_sec_km", sa.Float(), nullable=True),
        sa.Column("ngp_sec_km", sa.Float(), nullable=True),
        sa.Column("hr_drift_pct", sa.Float(), nullable=True),
        sa.Column("aerobic_decoupling_pct", sa.Float(), nullable=True),
        sa.Column("zone_distribution", sa.JSON(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_activity_metrics_activity_id", "activity_metrics", ["activity_id"], unique=True)
    op.create_index("ix_activity_metrics_athlete_id", "activity_metrics", ["athlete_id"])

    op.create_table(
        "load_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("ctl", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("atl", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("tsb", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("acwr", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("monotony", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("strain", sa.Float(), nullable=False, server_default="0.0"),
        sa.UniqueConstraint("athlete_id", "date", name="uq_load_history_athlete_id_date"),
    )
    op.create_index("ix_load_history_athlete_id", "load_history", ["athlete_id"])

    op.create_table(
        "race_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("race_name", sa.String(255), nullable=False),
        sa.Column("race_date", sa.Date(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("elevation_gain_m", sa.Float(), nullable=True),
        sa.Column("goal_time_sec", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Enum("A", "B", "C", name="priority"), nullable=False, server_default="A"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_race_targets_athlete_id", "race_targets", ["athlete_id"])


def downgrade() -> None:
    op.drop_table("race_targets")
    op.drop_table("load_history")
    op.drop_table("activity_metrics")
    op.drop_table("activities")
    op.drop_table("strava_credentials")
    op.drop_table("athlete_profiles")
    op.drop_table("athletes")
    op.execute("DROP TYPE IF EXISTS priority")
    op.execute("DROP TYPE IF EXISTS units")
