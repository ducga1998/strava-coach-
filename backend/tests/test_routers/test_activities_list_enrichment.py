"""GET /activities/ surfaces hrTSS + effort from the joined metrics row.

Also exercises the classify_effort helper across its thresholds.
"""
import asyncio
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.metrics import ActivityMetrics
from app.routers.activities import classify_effort


# -- classify_effort -------------------------------------------------

def test_classify_effort_hard_on_high_z4_z5() -> None:
    assert classify_effort({"z4_pct": 15.0, "z5_pct": 10.0}) == "hard"


def test_classify_effort_tempo_on_z3_block() -> None:
    # Z3=25, Z4=5 → hard band is 5%, so "tempo" wins.
    assert classify_effort({"z3_pct": 25.0, "z4_pct": 5.0}) == "tempo"


def test_classify_effort_easy_when_mostly_aerobic() -> None:
    assert (
        classify_effort({"z1_pct": 10.0, "z2_pct": 80.0, "z3_pct": 10.0})
        == "easy"
    )


def test_classify_effort_none_when_no_zone_data() -> None:
    assert classify_effort(None) is None
    assert classify_effort({}) is None


# -- endpoint --------------------------------------------------------

def _seed_activity_with_metrics(session: AsyncSession) -> None:
    session.add(Athlete(id=1, strava_athlete_id=1001))
    session.add(
        Activity(
            id=1,
            athlete_id=1,
            strava_activity_id=900001,
            name="Tempo intervals",
            sport_type="Run",
            start_date=datetime(2026, 4, 20, 6, 0, 0),
            distance_m=12000,
            elapsed_time_sec=4080,
            total_elevation_gain_m=120,
            processing_status="done",
        )
    )
    session.add(
        ActivityMetrics(
            activity_id=1,
            athlete_id=1,
            hr_tss=78.2,
            zone_distribution={"z1_pct": 5, "z2_pct": 40, "z3_pct": 35, "z4_pct": 15, "z5_pct": 5},
        )
    )
    asyncio.run(session.commit())


def _seed_activity_without_metrics(session: AsyncSession) -> None:
    session.add(Athlete(id=2, strava_athlete_id=2002))
    session.add(
        Activity(
            id=2,
            athlete_id=2,
            strava_activity_id=900002,
            name="Queued run",
            sport_type="Run",
            start_date=datetime(2026, 4, 21, 6, 0, 0),
            distance_m=8000,
            elapsed_time_sec=2700,
            total_elevation_gain_m=50,
            processing_status="queued",
        )
    )
    asyncio.run(session.commit())


def test_list_exposes_hr_tss_and_effort_for_processed_activity(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_activity_with_metrics(db_session)
    response = client.get("/activities/?athlete_id=1")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["hr_tss"] == 78.2
    # z4+z5 = 20 → hard
    assert row["effort"] == "hard"


def test_list_returns_nulls_when_metrics_missing(
    client: TestClient, db_session: AsyncSession
) -> None:
    _seed_activity_without_metrics(db_session)
    response = client.get("/activities/?athlete_id=2")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["hr_tss"] is None
    assert rows[0]["effort"] is None
    # Existing contract preserved.
    assert rows[0]["processing_status"] == "queued"
