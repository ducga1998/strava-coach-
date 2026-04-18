import asyncio
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.activity_ingestion import _push_description


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
