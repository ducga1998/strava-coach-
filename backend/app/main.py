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
        allow_origins=[settings.frontend_url],
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


app = create_app()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
