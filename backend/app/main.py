from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import activities, auth, dashboard, onboarding, targets, webhook


def create_app() -> FastAPI:
    api = FastAPI(title="Strava AI Coach API")
    register_middleware(api)
    register_routes(api)
    return api


def register_middleware(api: FastAPI) -> None:
    api.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_cors_origins(
            settings.frontend_url, settings.cors_origins
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def register_routes(api: FastAPI) -> None:
    api.include_router(auth.router)
    api.include_router(webhook.router)
    api.include_router(onboarding.router)
    api.include_router(targets.router)
    api.include_router(activities.router)
    api.include_router(dashboard.router)


def allowed_cors_origins(frontend_url: str, extra_origins: str) -> list[str]:
    local_origin = normalize_origin(frontend_url)
    origins = set(parse_cors_origins(extra_origins))
    origins.add(local_origin)
    origins.add(local_origin.replace("localhost", "127.0.0.1"))
    return sorted(origin for origin in origins if origin)


def parse_cors_origins(value: str) -> list[str]:
    return [normalize_origin(origin) for origin in value.split(",") if origin.strip()]


def normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


app = create_app()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
