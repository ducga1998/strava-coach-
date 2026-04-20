# Admin Dashboard — Design Spec

**Date:** 2026-04-20
**Scope:** Admin-only dashboard bolted onto the existing Strava Coach FastAPI + React app. Covers athlete management, versioned LLM prompts with per-version model pinning, and debrief evaluation (manual ratings + automated rule checks + per-version aggregates).

---

## 1. Goals & Non-Goals

### Goals
- Give 2–5 admins a dedicated UI to operate the coach in production.
- Replace the hardcoded `SYSTEM_PROMPT` with a versioned, DB-driven prompt registry that the debrief agent reads at runtime.
- Pin the Claude model (`claude-opus-4-7` / `claude-sonnet-4-6` / `claude-haiku-4-5`) per prompt version so tuning + model choice travel together.
- Record every debrief generation as a `DebriefRun` so admins can review, rate, and compare prompt versions objectively.
- Run deterministic quality rules (banned phrases, missing numbers, empty fields, missing Vietnamese food, missing time marker) on every successful debrief and surface the flags in a review queue.

### Non-Goals (explicit)
- No multi-provider LLM abstraction (OpenAI / Gemini). Claude-only.
- No A/B traffic splitting between prompt versions. Exactly one version is active at a time.
- No per-athlete prompt overrides in v1.
- No admin impersonation ("view as athlete").
- No hard-delete of athletes via the UI (do it at the DB if needed).
- No athlete-facing 👍/👎 feedback button.
- No invitation emails — new admins created via CLI, password shared out of band.
- No RBAC — every admin has full powers.

---

## 2. Architecture

### 2.1 Approach
Parallel admin module in the same FastAPI app (`backend/app/admin/`) with its own routers, models, and auth dependency. Athlete-facing code is untouched except for two small hooks: the debrief agent reads the active prompt from `prompt_registry`, and the webhook worker skips athletes where `disabled_at IS NOT NULL`.

Frontend ships as a lazy-loaded chunk under `/admin/*` inside the existing Vite app. Athlete bundle only grows by a route stub.

### 2.2 File layout

```
backend/app/
├── admin/
│   ├── __init__.py
│   ├── auth.py                     # password hashing (argon2id), session create/validate, require_admin dep
│   ├── cli.py                      # python -m app.admin.cli create-admin ...
│   ├── models.py                   # Admin, AdminSession, PromptVersion,
│   │                               # DebriefRun, DebriefRating, DebriefAutoFlag
│   ├── schemas.py                  # Pydantic request/response
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── admin_auth.py           # /admin/auth/*
│   │   ├── admin_users.py          # /admin/users/*
│   │   ├── admin_prompts.py        # /admin/prompts/*
│   │   ├── admin_debriefs.py       # /admin/debriefs/*
│   │   └── admin_stats.py          # /admin/stats/*
│   └── services/
│       ├── prompt_registry.py      # get_active() → PromptVersion
│       ├── eval_rules.py           # pure functions running the 5 quality rules
│       └── admin_invite.py         # create admin row + generate password

backend/app/agents/
├── debrief_graph.py                # MODIFIED — reads prompt_registry, records DebriefRun, runs eval_rules
├── prompts.py                      # build_debrief_prompt() stays code; SYSTEM_PROMPT constant removed
backend/alembic/versions/
└── XXXX_admin_dashboard.py         # creates all admin tables + athletes.disabled_at + seeds prompt v1

frontend/src/
├── admin/                          # lazy-loaded
│   ├── AdminApp.tsx                # <RequireAdmin> wrapper + nested routes
│   ├── api.ts                      # axios (withCredentials) + useQuery/useMutation hooks
│   ├── components/
│   │   ├── AdminNav.tsx
│   │   ├── DataTable.tsx
│   │   ├── DiffView.tsx
│   │   └── RequireAdmin.tsx
│   ├── types.ts                    # mirrors backend schemas.py, no any
│   └── pages/
│       ├── Login.tsx
│       ├── Home.tsx
│       ├── Users.tsx
│       ├── UserDetail.tsx
│       ├── Prompts.tsx
│       ├── PromptVersion.tsx
│       ├── PromptNew.tsx
│       ├── Debriefs.tsx
│       └── DebriefDetail.tsx
└── App.tsx                         # ADD: <Route path="/admin/*" element={<lazy AdminApp />} />
```

### 2.3 Dependency direction
`admin/` may import from `app.models.*` (reads athletes/activities) but the reverse is forbidden. `debrief_graph` has one new dependency: `admin.services.prompt_registry`. This is explicitly allowed — it's a read of a domain setting, not a coupling to admin concerns.

---

## 3. Data Model

All new tables live in `backend/app/admin/models.py`. One Alembic migration creates everything plus the `athletes.disabled_at` column and seeds prompt v1 from the current hardcoded text.

### 3.1 `admins`
| col | type | notes |
|---|---|---|
| `id` | int PK | |
| `email` | varchar(255) | unique, lowercased, indexed |
| `password_hash` | varchar(255) | argon2id |
| `name` | varchar(100) nullable | display name |
| `disabled_at` | timestamptz nullable | soft-disable admin access |
| `created_at` | timestamptz default now() | |
| `last_login_at` | timestamptz nullable | |

### 3.2 `admin_sessions`
Opaque session tokens. The raw token is sent as the `admin_session` HttpOnly cookie; only its sha256 is stored.

| col | type | notes |
|---|---|---|
| `id` | int PK | |
| `admin_id` | int FK admins | |
| `token_hash` | char(64) | unique, indexed |
| `expires_at` | timestamptz | indexed for cleanup |
| `revoked_at` | timestamptz nullable | logout / password change |
| `user_agent` | varchar(255) nullable | for "active sessions" display |
| `created_at` | timestamptz default now() | |

### 3.3 `prompt_versions`
Heart of the feature. Exactly one row has `is_active=true` at any time.

| col | type | notes |
|---|---|---|
| `id` | int PK | |
| `version_number` | int unique | monotonic; displayed as `v1`, `v2`, … |
| `name` | varchar(100) | short label, e.g. `baseline-vmm` |
| `system_prompt` | text | full prompt body, admin-editable |
| `model` | varchar(50) | one of `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5` |
| `is_active` | boolean default false | **partial unique index** `WHERE is_active = true` |
| `notes` | text nullable | changelog entry for this version |
| `created_by` | int FK admins nullable | null for seeded v1 |
| `created_at` | timestamptz default now() | |
| `activated_at` | timestamptz nullable | most recent activation |
| `deactivated_at` | timestamptz nullable | when it was replaced |

**Invariant:** the partial unique index guarantees at most one active version. The `POST /admin/prompts/:id/activate` endpoint runs the swap in a single transaction so there is never a window with zero active versions.

### 3.4 `debrief_runs`
One row per debrief generation (LLM-successful *or* fallback).

| col | type | notes |
|---|---|---|
| `id` | int PK | |
| `activity_id` | int FK activities | indexed |
| `athlete_id` | int FK athletes | indexed |
| `prompt_version_id` | int FK prompt_versions | indexed |
| `model` | varchar(50) | **snapshot of version.model at run time** |
| `input_tokens` | int nullable | |
| `output_tokens` | int nullable | |
| `latency_ms` | int | |
| `tool_use_ok` | boolean | Claude returned `submit_debrief` cleanly |
| `fallback_used` | boolean | deterministic fallback fired |
| `raw_output` | jsonb nullable | the 5 tool-call fields |
| `created_at` | timestamptz default now() | indexed DESC |

The `model` column is intentionally denormalised: prompt text or model can be edited on the version row without rewriting history.

### 3.5 `debrief_ratings`
| col | type | notes |
|---|---|---|
| `debrief_run_id` | int PK FK | one rating per run; overwrites allowed |
| `admin_id` | int FK admins | |
| `thumb` | enum(`up`,`down`) | |
| `notes` | text nullable | |
| `created_at` | timestamptz default now() | |

### 3.6 `debrief_auto_flags`
| col | type | notes |
|---|---|---|
| `id` | int PK | |
| `debrief_run_id` | int FK | indexed |
| `rule_name` | varchar(50) | `banned_phrase` / `missing_number` / `empty_field` / `no_vietnamese_food` / `no_time_marker` |
| `detail` | text nullable | e.g. `found 'keep it up' in technical_insight` |
| `created_at` | timestamptz default now() | |

### 3.7 Modification to existing model
Add `athletes.disabled_at: timestamptz nullable` (same Alembic migration). The debrief worker checks this and skips disabled athletes. Athlete dashboards still read.

---

## 4. Backend API

All endpoints under `/admin/*`, every route depends on `require_admin`. Auth via HttpOnly cookie `admin_session` with `SameSite=Lax` (same-origin SPA → no explicit CSRF).

### 4.1 Auth
| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/admin/auth/login` | `{email, password}` | 200 + Set-Cookie; 401 on fail |
| POST | `/admin/auth/logout` | — | 204; revokes current session |
| GET | `/admin/auth/me` | — | `{id, email, name}` or 401 |
| POST | `/admin/auth/change-password` | `{current, new}` | 204 |

### 4.2 Users
| Method | Path | Notes |
|---|---|---|
| GET | `/admin/users?q=&disabled=&limit=&offset=` | paginated; `q` matches name / strava_athlete_id |
| GET | `/admin/users/:id` | detail with latest CTL/ATL/TSB/ACWR, activity_count, last_sync_at, disabled_at |
| PATCH | `/admin/users/:id/profile` | `{lthr?, max_hr?, threshold_pace_sec_km?, weight_kg?, units?}` |
| POST | `/admin/users/:id/disable` | sets `athletes.disabled_at = now()` |
| POST | `/admin/users/:id/enable` | clears `disabled_at` |
| POST | `/admin/users/:id/resync` | `{since?: date}` → BackgroundTasks |

### 4.3 Prompts
| Method | Path | Notes |
|---|---|---|
| GET | `/admin/prompts` | list + stats per version |
| GET | `/admin/prompts/:id` | full text + stats |
| POST | `/admin/prompts` | `{name, system_prompt, model, notes?, base_version_id?}` → creates inactive |
| POST | `/admin/prompts/:id/activate` | atomic swap in one transaction |
| GET | `/admin/prompts/:id/diff?against=:other_id` | unified text diff |

### 4.4 Debriefs
| Method | Path | Notes |
|---|---|---|
| GET | `/admin/debriefs?prompt_version_id=&rating=unrated\|up\|down&flagged=bool&athlete_id=&limit=&offset=` | queue filter |
| GET | `/admin/debriefs/:run_id` | raw_output + flags + rating + activity summary + input context |
| PUT | `/admin/debriefs/:run_id/rating` | `{thumb, notes?}` upsert |

### 4.5 Stats
| Method | Path | Notes |
|---|---|---|
| GET | `/admin/stats/overview` | totals: athletes, active (synced ≤ 7d), debriefs this week, 👍 rate |
| GET | `/admin/stats/prompt-versions` | per version: `{n_runs, n_rated, pct_up, pct_flagged, avg_latency_ms, total_tokens}` |

### 4.6 `require_admin` dependency
Pseudo-code:
```python
async def require_admin(request, db) -> Admin:
    raw = request.cookies.get("admin_session")
    if not raw: raise HTTPException(401)
    token_hash = sha256(raw).hexdigest()
    session = (await db.execute(
        select(AdminSession)
          .where(AdminSession.token_hash == token_hash,
                 AdminSession.revoked_at.is_(None),
                 AdminSession.expires_at > func.now())
    )).scalar_one_or_none()
    if not session: raise HTTPException(401)
    admin = await db.get(Admin, session.admin_id)
    if not admin or admin.disabled_at: raise HTTPException(401)
    return admin
```

---

## 5. Prompt Registry & Debrief Integration

### 5.1 `prompt_registry.get_active()`
- Returns the row where `is_active = true`.
- In-process cache with 30s TTL to avoid a DB hit on every webhook (invalidated when `/activate` runs by bumping a module-level version counter).
- Raises if zero active rows (should be impossible due to partial unique index + atomic swap, but defensively surfaced).

### 5.2 Changes to `debrief_graph.py`
```
BEFORE:
  from app.agents.prompts import SYSTEM_PROMPT, build_debrief_prompt
  client = anthropic.Anthropic(api_key=...)
  response = client.messages.create(model="claude-sonnet-4-6", system=SYSTEM_PROMPT, ...)

AFTER:
  version = await prompt_registry.get_active()
  start = time.monotonic()
  response = client.messages.create(model=version.model, system=version.system_prompt, ...)
  latency_ms = int((time.monotonic() - start) * 1000)
  # persist DebriefRun (success or fallback)
  run = DebriefRun(
      activity_id=..., athlete_id=..., prompt_version_id=version.id,
      model=version.model, input_tokens=response.usage.input_tokens,
      output_tokens=response.usage.output_tokens, latency_ms=latency_ms,
      tool_use_ok=..., fallback_used=..., raw_output=<tool call fields>,
  )
  db.add(run); await db.flush()
  if not run.fallback_used and run.tool_use_ok:
      flags = eval_rules.run_all(run.raw_output)
      db.add_all(DebriefAutoFlag(debrief_run_id=run.id, **f) for f in flags)
  await db.commit()
```

`build_debrief_prompt` (the user-message composer that interpolates structured metrics) stays as code. Only `SYSTEM_PROMPT` becomes DB-driven — the hardcoded constant in `backend/app/agents/prompts.py` is removed, and its current text is copied into the Alembic data migration as the seed body for prompt version 1. This is deliberate: the user-prompt composer has Python-side interpolation that's fragile to admin typos; the system prompt is pure prose where admin editing is safe.

---

## 6. Eval Rules

Pure functions in `admin/services/eval_rules.py`, each taking the 5-field dict and returning `list[dict]` of `{rule_name, detail}`.

| rule_name | trigger |
|---|---|
| `banned_phrase` | any of `great job`, `keep it up`, `listen to your body` (case-insensitive) in any field |
| `empty_field` | any required field is empty or whitespace-only |
| `missing_number` | a field has zero digit characters `[0-9]` |
| `no_vietnamese_food` | `nutrition_protocol` contains no keyword from {`phở`, `pho`, `nước mía`, `nuoc mia`, `cơm tấm`, `com tam`, `bánh mì`, `banh mi`, `cháo`, `chao`} (case-insensitive) |
| `no_time_marker` | `vmm_projection` contains no `h`, `hour`, or `:` |

Called only on successful LLM runs (skip fallbacks). All flags persisted — the review queue surfaces them.

---

## 7. Frontend

### 7.1 Routing
- `App.tsx` adds one route: `<Route path="/admin/*" element={<Suspense fallback={null}><AdminApp/></Suspense>}/>` via `React.lazy(() => import("./admin/AdminApp"))`.
- `AdminApp.tsx` wraps with `<RequireAdmin>` and declares nested routes for every admin page.

### 7.2 Auth guard
`RequireAdmin` calls `GET /admin/auth/me` via TanStack Query. 401 → navigate `/admin/login`. 200 → render children.

### 7.3 Pages
| Route | Purpose |
|---|---|
| `/admin/login` | email + password form |
| `/admin` | overview stats + active prompt card |
| `/admin/users` | table (name · strava_id · last_sync · CTL · ACWR · disabled?) |
| `/admin/users/:id` | profile form + [Disable/Enable] + [Force re-sync] + recent activities list |
| `/admin/prompts` | version list with aggregates |
| `/admin/prompts/:id` | full system_prompt readout + stats + [Activate] + [Diff vs…] selector |
| `/admin/prompts/new` | textarea form (pre-filled from active), model dropdown, notes |
| `/admin/debriefs` | queue + filters (prompt_version, rating, flagged, athlete) |
| `/admin/debriefs/:run_id` | 3-column: activity context · raw_output · flags + rating form |

### 7.4 Data access
- One file: `admin/api.ts` with an axios instance (`withCredentials: true`) + TanStack Query hooks per endpoint.
- Mutations invalidate the relevant query key.
- All response shapes typed in `frontend/src/admin/types.ts` (mirrors backend `schemas.py`). No `any`.

---

## 8. Security

- Passwords hashed with argon2id (via `argon2-cffi`), minimum 12 chars enforced server-side.
- Session tokens: 32 bytes from `secrets.token_urlsafe(32)`; stored as sha256 server-side. Default lifetime 14 days, sliding (extend on activity).
- Cookie flags: `HttpOnly=True`, `Secure=True` (prod), `SameSite=Lax`, `Path=/admin`.
- Rate limiting on `/admin/auth/login`: 5 attempts / 15 min per IP (use existing middleware if present, otherwise a tiny in-memory limiter behind a TODO to upgrade to Redis).
- Admin disable: setting `admins.disabled_at` immediately kills all sessions on next request (the dependency checks it every time).
- No Strava token is ever returned by admin endpoints — athlete detail exposes profile data only.
- CORS: admin endpoints only allowed from the configured `FRONTEND_URL` origin; `allow_credentials=True`.

---

## 9. Testing

Backend (`backend/tests/test_admin/`):
- `test_auth.py` — login success/fail, wrong password, disabled admin rejected, session expiry, logout revokes, session survives request.
- `test_users.py` — list pagination + filter, profile PATCH validates ranges, disable/enable toggles flag, resync triggers BackgroundTasks, unauth → 401.
- `test_prompts.py` — create version, activate atomically swaps `is_active`, diff endpoint, partial unique index blocks a second active row, rollback works.
- `test_debriefs.py` — rating upsert (2nd call overwrites), filters combine correctly.
- `test_eval_rules.py` — each rule fires on the seeded bad cases; none fire on a known-good fixture.
- `test_prompt_registry.py` — `get_active()` returns current row, cache TTL respected, invalidation after activate.

Frontend (`frontend/src/admin/__tests__/`):
- Type tests for api.ts responses.
- Smoke render of `Login`, `Users`, `PromptVersion` with MSW-mocked responses (if MSW is already in the project; otherwise skipped — backend tests are the ground truth).

Manual acceptance for the **login slice** (the first slice to ship):
1. Apply migration → tables + seed prompt v1 from current hardcoded text.
2. `python -m app.admin.cli create-admin --email=you@example.com` → prints password.
3. `uvicorn app.main:app --reload` + `npm run dev`.
4. Visit `/admin/login` → enter creds → lands on `/admin`.
5. `GET /admin/users` loads existing athletes.
6. Reload → session persists.
7. Logout → cookie cleared → redirect to login.

---

## 10. Rollout Order

Each slice is independently testable end-to-end:

1. **Login slice** — migration + seed + admin CLI + admin_auth router + `require_admin` dep + frontend `AdminApp` shell + `Login` + `Home` + `RequireAdmin`. User verifies login works.
2. **Users slice** — `admin_users` router + `Users` list + `UserDetail` + profile edit + disable/enable + resync.
3. **Prompts slice** — `prompt_versions` model wired in + `prompt_registry` + `admin_prompts` router + `debrief_graph` refactor + `Prompts` / `PromptVersion` / `PromptNew` pages.
4. **Eval slice** — `DebriefRun` recording in `debrief_graph` + `eval_rules` + `admin_debriefs` router + `Debriefs` / `DebriefDetail` pages.
5. **Stats slice** — `admin_stats` router + overview numbers + per-version aggregates on `Home` and `Prompts`.

---

## 11. Open Questions / Follow-ups

- **Cost telemetry:** `input_tokens`/`output_tokens` already available on `message.usage`; estimated USD cost per 1K tokens could be added to aggregates, but defer until we actually care.
- **Prompt import/export:** nice-to-have — markdown export of a version, import from YAML. Not v1.
- **Audit log:** every admin write action could hit an `admin_audit` table. Deferred; `created_by` on `prompt_versions` covers the highest-risk action.
- **Password reset flow:** currently CLI-only. Self-service reset would need email. Deferred.
