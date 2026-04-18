# Strava Coach — CI/CD Re-Plan (Cloudflare + Railway)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` (or `superpowers:subagent-driven-development`) to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Goal

Route deployments by code ownership:

1. Frontend changes deploy to Cloudflare Pages.
2. Backend changes deploy to Railway.

## Scope

- GitHub Actions workflow design and validation.
- Deployment secrets/variables contract.
- Promotion/rollback process.
- Operational checks for production deploy confidence.

## Non-Goals

- Re-architecting application code.
- Replacing Cloudflare or Railway providers.
- Building preview environments per PR (can be Phase 2 extension).

## Assumptions

- Default deploy branch is `main`.
- Frontend deploy target is Cloudflare Pages project `strava-coach`.
- Backend deploy target is a Railway service already created.
- Required secrets are configured in GitHub repository settings.

---

## Acceptance Criteria

- [ ] **AC1**: `push` to `main` changing `frontend/**` triggers frontend workflow and does not trigger backend workflow.
- [ ] **AC2**: `push` to `main` changing `backend/**` triggers backend workflow and does not trigger frontend workflow.
- [ ] **AC3**: Frontend workflow builds from `frontend/` and deploys `dist` to Cloudflare Pages successfully.
- [ ] **AC4**: Backend workflow deploys `backend/` only to Railway successfully.
- [ ] **AC5**: Both workflows are manually runnable via `workflow_dispatch`.
- [ ] **AC6**: Deployment runbook documents secrets, trigger rules, and rollback actions.

---

## Architecture Decision Matrix

| option | upside | downside | cost |
| --- | --- | --- | --- |
| Two path-filter workflows (chosen) | Clear ownership boundaries, lower accidental deploy risk, easier incident triage | Duplicate setup steps | Low |
| Single workflow with conditional jobs | Centralized file | Harder conditional logic and debugging | Medium |
| Provider-native auto deploy only (no Actions routing) | Minimal CI config | Weak monorepo path isolation and auditability | Low |

Decision: **Two workflow files** to maximize clarity and minimize blast radius.

---

## Phase 0 — Baseline Audit

### Task 0.1: Validate deployment boundaries

- [ ] Confirm frontend deploy artifacts are only `frontend/dist`.
- [ ] Confirm backend deploy root is only `backend/`.
- [ ] Confirm no shared file should trigger both deployments (except intentional workflow file edits).

### Task 0.2: Validate provider contracts

- [ ] Cloudflare: project exists and API token has Pages deploy permission.
- [ ] Railway: project/service/environment IDs or names are known and valid.

Deliverable:
- One-page deployment contract under `docs/deploy/github-actions.md`.

---

## Phase 1 — Path-Routed Auto Deploy (MVP)

### Task 1.1: Frontend workflow

- [ ] Trigger on `main` + paths:
  - `frontend/**`
  - `.github/workflows/deploy-frontend-cloudflare.yml`
- [ ] Setup Node 20 and install dependencies via `npm ci`.
- [ ] Build with `VITE_API_URL` injected from secrets.
- [ ] Deploy `frontend/dist` via Wrangler Pages deploy command.
- [ ] Add `concurrency` guard to cancel stale runs.

### Task 1.2: Backend workflow

- [ ] Trigger on `main` + paths:
  - `backend/**`
  - `scripts/deploy-backend-railway.sh`
  - `.github/workflows/deploy-backend-railway.yml`
- [ ] Use Railway CLI with token-based auth.
- [ ] Deploy with `railway up ... backend --path-as-root`.
- [ ] Add `concurrency` guard to cancel stale runs.

### Task 1.3: Manual execution parity

- [ ] Add `workflow_dispatch` on both workflows.
- [ ] Validate both can run without code changes.

Deliverables:
- `.github/workflows/deploy-frontend-cloudflare.yml`
- `.github/workflows/deploy-backend-railway.yml`

---

## Phase 2 — Hardening

### Task 2.1: Pre-deploy quality gates

- [ ] Frontend: run `npm run typecheck` before deploy.
- [ ] Backend: run smoke tests (`pytest -q backend/tests/test_main.py`) before deploy.

### Task 2.2: Failure observability

- [ ] Add clear step names and summary output for deployment target URL/id.
- [ ] Add failure notification integration (Slack/Discord/Webhook).

### Task 2.3: Environment safety

- [ ] Optionally gate production deploys using GitHub Environments approval.
- [ ] Restrict secret scope to production branch/environment.

Deliverables:
- Hardened workflows with explicit preflight checks and environment guardrails.

---

## Phase 3 — Rollback + Recovery

### Task 3.1: Frontend rollback runbook

- [ ] Document Cloudflare rollback path (promote prior deployment or re-deploy known-good commit).

### Task 3.2: Backend rollback runbook

- [ ] Document Railway rollback path (`railway redeploy` previous deployment or redeploy known-good commit).

### Task 3.3: Disaster drill

- [ ] Perform one simulated bad deploy and verify rollback time objective.

Deliverable:
- Incident rollback section in `docs/deploy/github-actions.md`.

---

## Secrets Contract

### Cloudflare

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `VITE_API_URL`

### Railway

- `RAILWAY_TOKEN`
- `RAILWAY_PROJECT_ID`
- `RAILWAY_ENVIRONMENT`
- `RAILWAY_SERVICE`

Policy:
- [ ] Secrets only in GitHub Actions secrets store.
- [ ] No provider secrets in repository files.

---

## AC -> Test Mapping

- **AC1** -> Test: commit touching only `frontend/src/App.tsx`; expect frontend workflow `success`, backend workflow `skipped`.
- **AC2** -> Test: commit touching only `backend/app/main.py`; expect backend workflow `success`, frontend workflow `skipped`.
- **AC3** -> Test: verify frontend run logs include build and Pages deploy command success.
- **AC4** -> Test: verify backend run logs show `backend --path-as-root` and deployment success.
- **AC5** -> Test: run both workflows via `workflow_dispatch` and verify green status.
- **AC6** -> Test: check runbook includes trigger rules, secrets list, and rollback steps.

---

## Risks and Mitigations

| risk | impact | mitigation |
| --- | --- | --- |
| Wrong path filters | Missed or accidental deploy | Add explicit path tests in first week and protect workflow changes with review |
| Secret misconfiguration | Deploy failures | Add preflight echo-free validation steps and secrets checklist |
| Provider CLI behavior drift | Runtime CI breakage | Pin toolchain versions where possible and keep runbook updated |

---

## Execution Order

1. Complete Phase 0 checks.
2. Ship Phase 1 workflows and run AC1-AC5 tests.
3. Add Phase 2 hardening in follow-up PR.
4. Finalize Phase 3 rollback drills and signoff.

## Definition of Done

- [ ] All Acceptance Criteria checked.
- [ ] `docs/deploy/github-actions.md` updated and approved.
- [ ] Two consecutive deploy cycles pass for frontend-only and backend-only changes.
