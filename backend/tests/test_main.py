from app.main import allowed_cors_origins


def test_allowed_cors_origins_includes_frontend_and_extra_origins() -> None:
    origins = allowed_cors_origins(
        "http://localhost:5173",
        "https://strava-coach.pages.dev, https://preview.pages.dev/",
    )

    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins
    assert "https://strava-coach.pages.dev" in origins
    assert "https://preview.pages.dev" in origins
