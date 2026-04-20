from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import allowed_cors_origins, app
from app.services.webhook_subscription import SubscriptionStatus


def test_health_reports_webhook_subscription_state() -> None:
    status = SubscriptionStatus(
        state="registered",
        subscription_id=999,
        callback_url="https://example.com/webhook/strava",
    )

    async def fake_ensure() -> SubscriptionStatus:
        return status

    with patch("app.main.ensure_webhook_subscription", fake_ensure):
        with TestClient(app) as client:
            body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["webhook"]["state"] == "registered"
    assert body["webhook"]["subscription_id"] == 999


def test_health_reports_failed_subscription_so_ops_see_outage() -> None:
    status = SubscriptionStatus(state="failed", error="HTTP 429: Rate Limit Exceeded")

    async def fake_ensure() -> SubscriptionStatus:
        return status

    with patch("app.main.ensure_webhook_subscription", fake_ensure):
        with TestClient(app) as client:
            body = client.get("/health").json()
    assert body["webhook"]["state"] == "failed"
    assert "429" in body["webhook"]["error"]


def test_allowed_cors_origins_includes_frontend_and_extra_origins() -> None:
    origins = allowed_cors_origins(
        "http://localhost:5173",
        "https://strava-coach.pages.dev, https://preview.pages.dev/",
    )

    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins
    assert "https://strava-coach.pages.dev" in origins
    assert "https://preview.pages.dev" in origins
