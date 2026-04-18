# GitHub Actions Auto Deploy

This repo uses path-based GitHub Actions deployment:

1. Frontend changes deploy to Cloudflare Pages.
2. Backend changes deploy to Railway.

## Trigger Rules

### Frontend workflow

File: `.github/workflows/deploy-frontend-cloudflare.yml`

Runs on `push` to `main` when files change under:

- `frontend/**`
- `.github/workflows/deploy-frontend-cloudflare.yml`

### Backend workflow

File: `.github/workflows/deploy-backend-railway.yml`

Runs on `push` to `main` when files change under:

- `backend/**`
- `scripts/deploy-backend-railway.sh`
- `.github/workflows/deploy-backend-railway.yml`

Both workflows also support manual trigger via `workflow_dispatch`.

## Required GitHub Secrets

Set these repository secrets in `Settings -> Secrets and variables -> Actions`.

Current setup status:

| secret | status |
| --- | --- |
| `CLOUDFLARE_API_KEY` | Configured |
| `CLOUDFLARE_ACCOUNT_ID` | Configured |
| `CLOUDFLARE_EMAIL` | Configured |
| `VITE_API_URL` | Configured |
| `RAILWAY_TOKEN` | Configured |
| `RAILWAY_PROJECT_ID` | Configured |
| `RAILWAY_ENVIRONMENT` | Configured |
| `RAILWAY_SERVICE` | Configured |

### Frontend (Cloudflare)

- `CLOUDFLARE_API_KEY`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_EMAIL`
- `VITE_API_URL`

Notes:

- `CLOUDFLARE_API_KEY` is the Cloudflare Global API Key paired with `CLOUDFLARE_EMAIL`.
- `CLOUDFLARE_ACCOUNT_ID` is configured as `b486fb51a808d6c53183f43594357793`.
- `VITE_API_URL` is configured as `https://backend-production-3f79.up.railway.app`.

### Backend (Railway)

- `RAILWAY_TOKEN`
- `RAILWAY_PROJECT_ID`
- `RAILWAY_ENVIRONMENT`
- `RAILWAY_SERVICE`

Notes:

- `RAILWAY_TOKEN` is a Railway project token scoped to project `strava-coach` and environment `production`.
- `RAILWAY_PROJECT_ID` is configured as `5cb5a09f-8cc0-4f69-a348-48fd2f696dde`.
- `RAILWAY_ENVIRONMENT` is configured as `production`.
- `RAILWAY_SERVICE` is configured as `backend`.

## Behavior

- Frontend workflow builds `frontend/` and deploys `frontend/dist` to Cloudflare Pages project `strava-coach`.
- Frontend workflow runs `npm run typecheck` before build.
- Backend workflow runs `python -m pytest -q tests/test_main.py` before deploy.
- Backend workflow deploys only the `backend/` directory to Railway via `railway up ... backend --path-as-root`.
- Workflows use `concurrency` to avoid overlapping deploys of the same target.

## Current Production Targets

| layer | provider | target |
| --- | --- | --- |
| Frontend | Cloudflare Pages | `https://strava-coach.pages.dev` |
| Backend | Railway | `https://backend-production-3f79.up.railway.app` |

## Rollback

Frontend rollback:

```bash
cd frontend
npx wrangler pages deployment list --project-name strava-coach
npx wrangler pages deployment tail --project-name strava-coach
```

Use Cloudflare Pages dashboard to promote a previous deployment, or re-run the workflow from a known-good commit.

Backend rollback:

```bash
cd backend
railway service status --service backend
railway redeploy --service backend --environment production
```

For a bad code deploy, re-run the backend workflow from a known-good commit or redeploy that commit from local checkout.

## Manual Deployment

From GitHub Actions tab:

1. Open `Deploy Frontend to Cloudflare` or `Deploy Backend to Railway`.
2. Click `Run workflow`.
