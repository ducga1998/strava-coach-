from fastapi.testclient import TestClient

from app.config import settings


def test_webhook_challenge(client: TestClient) -> None:
    response = client.get(
        "/webhook/strava",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "abc123",
            "hub.verify_token": settings.strava_verify_token,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"hub.challenge": "abc123"}


def test_webhook_bad_verify_token(client: TestClient) -> None:
    response = client.get(
        "/webhook/strava",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "abc123",
            "hub.verify_token": "wrong",
        },
    )
    assert response.status_code == 403
