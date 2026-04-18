import asyncio
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.metrics import ActivityMetrics
from app.services.activity_ingestion import _persist_activity, _push_description


def _mock_activity(debrief: dict | None = None, *, strava_id: int = 12345) -> MagicMock:
    activity = MagicMock()
    activity.id = 1
    activity.strava_activity_id = strava_id
    activity.athlete_id = 1
    activity.debrief = debrief
    return activity


def _mock_metrics(
    hr_tss: float = 72.0,
    hr_drift_pct: float = 4.1,
    decoupling_pct: float = 3.8,
    z2_pct: float = 68.0,
) -> MagicMock:
    m = MagicMock()
    m.hr_tss = hr_tss
    m.hr_drift_pct = hr_drift_pct
    m.aerobic_decoupling_pct = decoupling_pct
    m.zone_distribution = {"z2_pct": z2_pct}
    return m


def _mock_session(metrics: MagicMock | None, load: MagicMock | None = None) -> AsyncMock:
    session = AsyncMock()
    results = []
    for val in [metrics, load]:
        r = MagicMock()
        r.scalar_one_or_none.return_value = val
        results.append(r)
    session.execute.side_effect = results
    return session


def test_push_description_skipped_when_flag_off() -> None:
    async def run() -> None:
        activity = _mock_activity(debrief={"next_session_action": "Easy run"})
        mock_client = AsyncMock()
        with patch("app.services.activity_ingestion.settings") as s:
            s.strava_push_description = False
            s.frontend_url = "http://localhost:5173"
            await _push_description(AsyncMock(), activity, mock_client, "tok")
        mock_client.update_activity_description.assert_not_called()

    asyncio.run(run())


def test_push_description_skipped_when_no_debrief() -> None:
    async def run() -> None:
        activity = _mock_activity(debrief=None)
        mock_client = AsyncMock()
        with patch("app.services.activity_ingestion.settings") as s:
            s.strava_push_description = True
            s.frontend_url = "http://localhost:5173"
            await _push_description(AsyncMock(), activity, mock_client, "tok")
        mock_client.update_activity_description.assert_not_called()

    asyncio.run(run())


def test_push_description_calls_client_with_formatted_text() -> None:
    async def run() -> None:
        activity = _mock_activity(debrief={"next_session_action": "VMM 8w: easy trail"})
        session = _mock_session(metrics=_mock_metrics(), load=None)
        mock_client = AsyncMock()
        with patch("app.services.activity_ingestion.settings") as s:
            s.strava_push_description = True
            s.frontend_url = "http://localhost:5173"
            await _push_description(session, activity, mock_client, "tok")
        mock_client.update_activity_description.assert_called_once()
        _, _, description = mock_client.update_activity_description.call_args[0]
        assert "TSS 72" in description
        assert "VMM 8w: easy trail" in description
        assert "http://localhost:5173/activities/1" in description

    asyncio.run(run())


def test_push_description_swallows_http_error() -> None:
    async def run() -> None:
        activity = _mock_activity(debrief={"next_session_action": "Easy Z2"})
        session = _mock_session(metrics=_mock_metrics(), load=None)
        mock_client = AsyncMock()
        mock_client.update_activity_description.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=MagicMock(status_code=403)
        )
        with patch("app.services.activity_ingestion.settings") as s:
            s.strava_push_description = True
            s.frontend_url = "http://localhost:5173"
            await _push_description(session, activity, mock_client, "tok")  # must not raise
        mock_client.update_activity_description.assert_called_once()

    asyncio.run(run())


def test_persist_activity_updates_existing_strava_activity(
    db_session: AsyncSession,
) -> None:
    async def run() -> None:
        db_session.add(Athlete(id=1, strava_athlete_id=1001))
        db_session.add(
            Activity(
                athlete_id=1,
                strava_activity_id=12345,
                name="Old title",
                sport_type="Run",
            )
        )
        await db_session.commit()

        await _persist_activity(
            db_session,
            Activity(
                athlete_id=1,
                strava_activity_id=12345,
                name="New title",
                sport_type="TrailRun",
            ),
        )
        await db_session.commit()

        result = await db_session.execute(
            select(Activity).where(Activity.strava_activity_id == 12345)
        )
        activities = result.scalars().all()
        assert len(activities) == 1
        assert activities[0].name == "New title"
        assert activities[0].sport_type == "TrailRun"

    asyncio.run(run())


def test_persist_activity_clears_existing_metrics_for_recompute(
    db_session: AsyncSession,
) -> None:
    async def run() -> None:
        db_session.add(Athlete(id=1, strava_athlete_id=1001))
        activity = Activity(id=1, athlete_id=1, strava_activity_id=12345)
        db_session.add(activity)
        db_session.add(ActivityMetrics(activity_id=1, athlete_id=1, tss=20.0))
        await db_session.commit()

        await _persist_activity(
            db_session,
            Activity(athlete_id=1, strava_activity_id=12345, name="Recomputed"),
        )
        await db_session.commit()

        metrics = await db_session.scalar(
            select(ActivityMetrics).where(ActivityMetrics.activity_id == 1)
        )
        assert metrics is None

    asyncio.run(run())
