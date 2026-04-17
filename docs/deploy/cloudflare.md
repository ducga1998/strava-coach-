# Cloudflare Deployment

This repo can deploy the React/Vite frontend to Cloudflare Pages as-is. The FastAPI backend cannot run on Cloudflare Pages or standard Workers without a rewrite, so keep it on a Python host and point Pages at that API origin.

## Recommended Topology

| layer | target | reason |
| --- | --- | --- |
| Frontend | Cloudflare Pages | Static Vite build, fast global CDN, branch previews |
| Backend API | Python host such as Fly.io, Render, Railway, ECS, or a VPS | Current app is FastAPI plus Postgres and Redis |
| Database | Managed Postgres | Required by `DATABASE_URL` |
| Queue/cache | Managed Redis | Required by `REDIS_URL` and worker tasks |
| Edge proxy | Optional Cloudflare Worker later | Useful for same-origin `/api/*` routing, not required for first deploy |

## Cloudflare Pages Setup

Create a Pages project connected to this repository.

Build settings:

| setting | value |
| --- | --- |
| Root directory | `frontend` |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Node version | `20` |

Environment variables:

| name | example | notes |
| --- | --- | --- |
| `VITE_API_URL` | `https://api.strava-coach.example.com` | Public backend API base URL used by the Vite build |

The frontend includes:

| file | purpose |
| --- | --- |
| `frontend/wrangler.jsonc` | Wrangler Pages project config |
| `frontend/public/_redirects` | SPA fallback so React Router paths work on refresh |
| `frontend/public/_headers` | Basic static security and asset cache headers |
| `frontend/.env.production.example` | Required production Vite variable example |

## Direct Deploy

Use this when deploying from your machine instead of Git integration:

```bash
cd frontend
export VITE_API_URL="https://api.strava-coach.example.com"
npm run build
npx wrangler login
npx wrangler whoami
npx wrangler pages deploy dist --project-name strava-coach
```

Or after authentication:

```bash
cd frontend
export VITE_API_URL="https://api.strava-coach.example.com"
npm run pages:deploy
```

## Backend Production Variables

Set these on the Python backend host:

```bash
DATABASE_URL="postgresql+asyncpg://..."
REDIS_URL="redis://..."
STRAVA_CLIENT_ID="..."
STRAVA_CLIENT_SECRET="..."
STRAVA_VERIFY_TOKEN="..."
STRAVA_AUTH_CALLBACK_URL="https://api.strava-coach.example.com/auth/callback"
STRAVA_WEBHOOK_CALLBACK_URL="https://api.strava-coach.example.com/webhook/strava"
ENCRYPTION_KEY="base64-encoded-32-byte-key"
ANTHROPIC_API_KEY="..."
JWT_SECRET="..."
FRONTEND_URL="https://strava-coach.pages.dev"
CORS_ORIGINS="https://strava-coach.pages.dev,https://www.your-domain.com"
ENABLE_LLM_DEBRIEFS="false"
```

`FRONTEND_URL` controls OAuth redirect after Strava login. `CORS_ORIGINS` allows additional Pages preview or custom domains to call the API.

## Strava Dashboard

Configure Strava after the API has a public HTTPS URL:

| setting | value |
| --- | --- |
| Authorization callback domain | `api.strava-coach.example.com` |
| Webhook callback URL | `https://api.strava-coach.example.com/webhook/strava` |
| Webhook verify token | Same value as `STRAVA_VERIFY_TOKEN` |

## Health Checks

Before connecting the frontend:

```bash
curl -sS https://api.strava-coach.example.com/health
```

Expected:

```json
{"status":"ok"}
```

After Pages deploy, open the Pages URL and verify the browser can call:

```text
GET https://api.strava-coach.example.com/dashboard/load?athlete_id=1
```

## Known Constraint

Cloudflare can host this frontend immediately. Hosting the current backend on Cloudflare would require one of these follow-up projects:

| option | change required |
| --- | --- |
| Worker proxy | Keep FastAPI elsewhere, proxy `/api/*` from Cloudflare |
| Full Worker rewrite | Port FastAPI routes, SQL access, token encryption, and workers to TypeScript/Workers runtime |
| Cloudflare Hyperdrive | Keep Postgres external, use from Workers after backend rewrite |
