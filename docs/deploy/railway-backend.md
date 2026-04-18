# Railway Backend Deployment

This guide deploys the FastAPI backend in `backend/` to Railway.

## Goal

Deploy backend code with one command while keeping frontend deployment separate.

## Prerequisites

1. Install Railway CLI:

```bash
npm i -g @railway/cli
```

2. Login:

```bash
railway login
```

3. Link backend directory to your Railway project and service (first time only):

```bash
cd backend
railway link --project strava-coach --environment production --service backend
```

## Required Environment Variables

The `backend` Railway service is configured with:

```bash
DATABASE_URL=postgresql+asyncpg://... # references Railway Postgres private host
REDIS_URL=redis://... # references Railway Redis private host
STRAVA_WEBHOOK_CALLBACK_URL=https://backend-production-3f79.up.railway.app/webhook/strava
STRAVA_AUTH_CALLBACK_URL=https://backend-production-3f79.up.railway.app/auth/callback
FRONTEND_URL=https://strava-coach.pages.dev
CORS_ORIGINS=https://strava-coach.pages.dev
ENABLE_LLM_DEBRIEFS=false
```

Set these with real production values before enabling Strava login for real users:

```bash
STRAVA_CLIENT_ID=...
STRAVA_CLIENT_SECRET=...
STRAVA_VERIFY_TOKEN=...
ANTHROPIC_API_KEY=...
```

## Deploy Command

From repo root:

```bash
./scripts/deploy-backend-railway.sh
```

What this script validates before deploy:

1. `railway` CLI is installed.
2. CLI session is authenticated.
3. Project/service link resolves through `railway status`.

If all checks pass, it runs `railway up --service backend --environment production --detach` from `backend/`.

## Runtime Command

`backend/Procfile` defines Railway start command:

```text
web: python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

`backend/runtime.txt` and the Railway `RAILPACK_PYTHON_VERSION=3.12` service variable pin Railway to Python 3.12 because current pinned backend dependencies are not Python 3.13-compatible.

## Health Check

After deploy, verify:

```bash
curl -sS https://backend-production-3f79.up.railway.app/health
```

Expected response:

```json
{"status":"ok"}
```
