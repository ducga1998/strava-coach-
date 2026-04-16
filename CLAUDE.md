# Strava AI Coach — CLAUDE.md

Post-run AI debrief + training load dashboard for ultra/trail runners (VMM 160km focus).
Primary athlete: self-coached ultra runner, Strava + Garmin, training for VMM/UTMB.

---

## Read These First (in order)

| File | When to read |
|---|---|
| `PRD_COACHING.md` | Before any feature work — the coaching philosophy and what every metric means to a runner |
| `docs/agents/LEADER.md` | The full API contract + build sequence + quality gate |
| `docs/agents/BACKEND.md` | Before touching anything in `backend/` |
| `docs/agents/FRONTEND.md` | Before touching anything in `frontend/` |
| `docs/superpowers/plans/2026-04-16-strava-coach-master-plan.md` | Full task-by-task implementation plan with code |

---

## Current State

```
Phase 0  ✅ Infrastructure, Docker, DB models, OAuth routes, Webhook handler
Phase 1  ✅ Metrics engine — zones, GAP/NGP, hrTSS, HR drift, decoupling, CTL/ATL/TSB/ACWR
Phase 2  ✅ Onboarding API, Race targets API, Dashboard load API
Phase 3  ✅ LangGraph debrief agent — schema, prompts, graph, fallback
Phase 4  ✅ React frontend — Connect, Setup, Dashboard, ActivityDetail, Targets pages

Tests: 27 passed (backend only, pytest)
Frontend: built and in dist/, dev server runs on :5173
Backend: runs on :8000
```

**Remaining gaps (from plan self-review):**
- `GET /onboarding/suggest` — LTHR + Z2 pace auto-detect from history
- `DELETE /auth/revoke` — webhook cancel + token wipe
- Descent HR delta metric (`backend/app/metrics/slope.py`)
- Cadence drop metric (add to `backend/app/metrics/heart_rate.py`)
- ACWR warning banner in `frontend/src/pages/Dashboard.tsx`
- Telegram notification service (`backend/app/services/push_service.py`)
- Targets page UI (`frontend/src/pages/Targets.tsx`)

---

## Project Structure

```
strava-coach/
├── backend/                    ← Python FastAPI + LangGraph
│   ├── app/
│   │   ├── main.py             # FastAPI app factory
│   │   ├── config.py           # Pydantic Settings (reads .env)
│   │   ├── database.py         # SQLAlchemy async engine
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── routers/            # FastAPI route handlers
│   │   ├── services/           # Strava client, token encryption
│   │   ├── metrics/            # Pure functions — NO DB, NO HTTP
│   │   ├── agents/             # LangGraph debrief graph
│   │   └── workers/            # Background activity processing
│   ├── tests/                  # pytest (27 passing)
│   └── requirements.txt
├── frontend/                   ← React 18 + Vite + TypeScript
│   └── src/
│       ├── api/client.ts       # axios + TanStack Query hooks
│       ├── pages/              # Connect, Setup, Dashboard, ActivityDetail, Targets
│       ├── components/         # LoadChart, AcwrGauge, DebriefCard, PhaseIndicator
│       └── types/index.ts      # All API response types
├── docker-compose.yml          # postgres:16 + redis:7
├── docs/
│   ├── agents/                 # LEADER.md, BACKEND.md, FRONTEND.md
│   └── superpowers/plans/      # Implementation plan
└── PRD_COACHING.md             # Coaching philosophy (read this)
```

---

## Dev Commands

### Start infrastructure
```bash
docker compose up -d
# postgres on :5432, redis on :6379
```

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # then fill in values

# DB migration
alembic upgrade head

# Run server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/ -v

# Run specific test file
pytest tests/test_metrics/test_heart_rate.py -v
```

### Frontend
```bash
cd frontend
npm install

# Dev server → http://localhost:5173
npm run dev

# Type check
npm run typecheck

# Production build
npm run build
```

### Verify full stack
```bash
curl http://localhost:8000/health
# → {"status":"ok"}

# Open http://localhost:5173
# → Connect page visible
```

---

## Tech Stack

### Backend
| | |
|---|---|
| Framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2 async |
| DB | PostgreSQL 16 |
| Migrations | Alembic |
| HTTP client | httpx (async) |
| Encryption | AES-256-GCM (cryptography lib) |
| AI workflow | LangGraph 0.2 |
| LLM | Claude Sonnet 4.6 (`claude-sonnet-4-6`) via langchain-anthropic |
| Background | FastAPI BackgroundTasks |
| Testing | pytest + pytest-asyncio |

### Frontend
| | |
|---|---|
| Framework | React 18 + Vite |
| Language | TypeScript 5 strict |
| Routing | React Router v6 |
| Server state | TanStack Query v5 |
| Charts | Recharts |
| Styling | Tailwind CSS 3 |

---

## Hard Rules

**Backend:**
- All DB calls must be `await` — no sync SQLAlchemy
- `metrics/` functions are pure — no DB, no HTTP, no side effects
- Write failing test BEFORE implementing any metric function
- Never store Strava tokens in plaintext — always `encrypt()` before DB write
- Never log access tokens or refresh tokens

**Frontend:**
- All data fetching via `useQuery` hooks in `api/client.ts` — never `useEffect` + axios
- All API response types defined in `src/types/index.ts` — never `any`
- No metric computation in the browser — display only what the API returns
- `athlete_id` always comes from URL params or localStorage via `athleteId()` helper

**Shared:**
- `athlete_id` is passed as a query param in MVP — no JWT auth until Phase 5
- API contract in `docs/agents/LEADER.md` is authoritative — don't change endpoint shapes without updating that file
- Debrief output with generic phrases is a bug, not a style choice

---

## Agent Roles (for parallel work)

When dispatching subagents:

```
Backend work  → give agent: BACKEND.md + relevant plan tasks
Frontend work → give agent: FRONTEND.md + relevant plan tasks
Review/check  → give agent: LEADER.md API contract + quality gate
```

Backend and frontend agents work independently. They share only the API contract in LEADER.md.
Never let either agent touch the other's directory.

---

## Key Metric Interpretations (quick ref)

| Metric | Threshold | Coaching meaning |
|---|---|---|
| HR Drift | > 5% concern, > 8% flag | Went out too hard or aerobic base not deep enough |
| Aerobic Decoupling | > 5% concern, > 8% flag | Duration exceeded current base fitness |
| ACWR | 0.8–1.3 green, 1.3–1.5 yellow, > 1.5 red | Injury risk compass — most important number |
| TSB | < -20 too fatigued, +5 to +15 race-day target | Form / readiness |
| Descent HR Delta | > 0 concern, > +8 flag | Quad weakness — VMM race-specific risk |
| Cadence Drop | > 5% flag | Neuromuscular fatigue |
| Zone 3 time | > 30% of easy run | Junk miles — erases recovery purpose |

---

## Environment Variables (.env)

```env
# Backend — backend/.env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/stravacoach
REDIS_URL=redis://localhost:6379/0
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_VERIFY_TOKEN=           # random 32 chars
STRAVA_WEBHOOK_CALLBACK_URL=   # full public URL for webhook
ENCRYPTION_KEY=                # base64(os.urandom(32))
ANTHROPIC_API_KEY=
JWT_SECRET=
FRONTEND_URL=http://localhost:5173

# Frontend — frontend/.env.local
VITE_API_URL=http://localhost:8000
```

---

## Commit Style

```
feat: add descent HR delta metric for VMM-specific analysis
feat: ACWR warning banner on dashboard when > 1.5
fix: hr_drift excludes walk-break samples at velocity < 0.5 m/s
test: cadence drop edge case with empty cadence stream
chore: alembic migration for descent_hr_delta column
```
