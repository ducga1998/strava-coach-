# Strava description clarity + user feedback loop — Design

**Date**: 2026-04-20
**Status**: Approved (brainstorm phase)
**Scope**: 1 backend router, 1 migration, 2 new frontend pages, 1 nav link, description format refresh

---

## Problem

1. The Strava activity description currently produced by `format_strava_description()` packs 6+ metrics per line separated by `·`. On mobile Strava it reads as a dense blob — hard to scan.
2. There is no way for the athlete to tell us when a debrief is wrong, unrealistic, or tonally off. The product iterates on LLM prompts blind.

## Goals

- Make the Strava description scannable in one glance on a phone.
- Give every debrief a 1-tap feedback link the runner can use without signing in.
- Surface the feedback stream to admins so prompt iteration is grounded in real reactions.
- Keep MVP surface area small: one new table, four endpoints, two new pages.

## Non-goals

- Auth / login flow for feedback submission (app-wide decision: no JWT until Phase 5).
- Reply-to-feedback / two-way conversation.
- CSV export of feedback from admin dashboard.
- Linking feedback rows to `debrief_runs.id` at the column level (admin can join via `activity_id` + nearest `created_at` when needed).
- Rate-limiting at the API layer (no abuse surface expected at MVP).

---

## Architecture

```
Strava activity description (auto-pushed after ingestion)
    ├─ format: Grouped 3 blocks (metrics / coaching / links)
    └─ new link at bottom: 💬 Feedback → /feedback/<activity_id>?athlete_id=<id>

Public Feedback page (frontend)
    ├─ Route: /feedback/:activityId
    ├─ Layout: mobile-first, warm conversational tone (Vietnamese primary)
    ├─ Form: thumb up/down + optional comment
    └─ Submits to POST /feedback

Admin Feedback list (frontend, behind RequireAdmin)
    ├─ Route: /admin/feedback (new nav link)
    ├─ Layout: timeline with filter chips (All / 👎 / 👍 / Unread)
    └─ Reads GET /admin/feedback + PATCH .../read

Backend
    ├─ New table: user_feedback
    ├─ New router: app/routers/feedback.py
    └─ Description builder: updated signature + new layout
```

Separation of concerns:

- `user_feedback` is a new, independent table. It does **not** reuse `DebriefRating` (which is admin-owned internal quality ratings — a different concept).
- Public feedback API never touches admin session middleware; admin endpoints use the existing `RequireAdmin` dependency.
- Description builder stays pure (no DB, no HTTP) — caller supplies `feedback_url` the same way it supplies `deep_dive_url`.

---

## Data model

New table `user_feedback`:

```sql
CREATE TABLE user_feedback (
  id            SERIAL PRIMARY KEY,
  activity_id   INT  NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
  athlete_id    INT  NOT NULL REFERENCES athletes(id)   ON DELETE CASCADE,
  thumb         TEXT NOT NULL CHECK (thumb IN ('up','down')),
  comment       TEXT,
  read_at       TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_user_feedback_created  ON user_feedback(created_at DESC);
CREATE INDEX ix_user_feedback_activity ON user_feedback(activity_id);
CREATE INDEX ix_user_feedback_unread   ON user_feedback(read_at) WHERE read_at IS NULL;
```

Decisions:

- **No `UNIQUE (activity_id, athlete_id)`** — a runner may resubmit after changing their mind or adding detail. Admin sees the timeline.
- **`read_at TIMESTAMPTZ` not `is_read BOOLEAN`** — stores when it was read for future auditability; unread filter is `read_at IS NULL`.
- **No `debrief_run_id` column in MVP** — reduces coupling. If prompt-correlation becomes a hot path, add it as a nullable FK in a follow-up migration.
- Alembic migration lives at `backend/migrations/versions/003_user_feedback.py` with both `upgrade()` and `downgrade()` implemented (drop indexes + drop table).

SQLAlchemy model: `backend/app/models/feedback.py` — `UserFeedback(Base)` following the existing project pattern (see `backend/app/models/metrics.py` for the tz-aware timestamp convention).

---

## Backend API

All routes in a new file `backend/app/routers/feedback.py`. Registered in `backend/app/main.py` alongside existing routers.

### Public — no auth

**`POST /feedback`**

Request body:
```json
{
  "activity_id": 42,
  "athlete_id": 1,
  "thumb": "up" | "down",
  "comment": "optional, up to 2000 chars"
}
```

Validation:
- `thumb` must be `"up"` or `"down"` (Pydantic literal).
- `comment` is optional, max 2000 chars, leading/trailing whitespace stripped. Plain text — no HTML rendering anywhere in the UI, so no sanitizer needed beyond length.
- `activity_id` must exist **and** belong to `athlete_id`. On mismatch return `404` (do not distinguish "not found" from "not yours" — do not leak existence of other activities).

Response: `201 Created`
```json
{ "id": 17, "thumb": "up", "comment": null, "created_at": "2026-04-20T10:11:12+00:00" }
```

**`GET /feedback/activity/{activity_id}?athlete_id={id}`**

Returns the most recent feedback row for the `(activity_id, athlete_id)` pair, or `null`. Used by the Feedback page on mount to show "already submitted" state.

Response:
```json
{
  "existing": { "id": 17, "thumb": "up", "comment": null, "created_at": "..." } | null,
  "strava_activity_id": 9876543210
}
```

The `strava_activity_id` is included so the "submitted" confirmation can offer a "Back to Strava" deep link fallback (`https://www.strava.com/activities/<id>`).

### Admin — behind `RequireAdmin`

**`GET /admin/feedback?thumb=up|down&unread=true&cursor=<last_id>`**

All query params optional. Cursor-based pagination, 20 per page (ordered by `created_at DESC, id DESC`).

Response:
```json
{
  "items": [
    {
      "id": 17,
      "thumb": "down",
      "comment": "Next-action không thực tế...",
      "created_at": "2026-04-20T10:11:12+00:00",
      "read_at": null,
      "activity_id": 42,
      "activity_name": "Morning Run",
      "athlete_id": 1,
      "athlete_name": "duncan"
    }
  ],
  "next_cursor": 16
}
```

**`GET /admin/feedback/counts`**

Returns `{ all, up, down, unread }`. Single query; cached on the frontend via TanStack Query `staleTime: 30s`.

**`PATCH /admin/feedback/{id}/read`**

Sets `read_at = now()` if null. Idempotent. Response: `204`.

### Testing

Backend tests in `backend/tests/test_routers/`:

- `test_feedback.py`
  - `POST` happy path → 201 and DB row.
  - `POST` invalid thumb → 422.
  - `POST` comment > 2000 chars → 422.
  - `POST` `activity_id` does not belong to `athlete_id` → 404.
  - `POST` nonexistent activity → 404.
  - Two consecutive submits → two rows (no dedupe).
  - `GET /feedback/activity/{id}` no existing feedback → 200 with `existing: null`.
  - `GET /feedback/activity/{id}` with existing → 200 returns most recent.

- `test_admin_feedback.py`
  - `GET /admin/feedback` unauthenticated → 401.
  - Authenticated GET with each filter combination (`thumb`, `unread`, none) returns correct items.
  - Cursor pagination returns correct `next_cursor` and empty on last page.
  - `PATCH .../read` sets `read_at`, is idempotent on second call.
  - `GET /admin/feedback/counts` returns accurate counts.

- `test_description_builder.py` — rewrite existing line-index assertions to content-contain assertions; add a test that `feedback_url` appears in the output and is on its own line.

---

## Description builder changes

File: `backend/app/services/description_builder.py`.

**New signature:**

```python
def format_strava_description(
    tss: float,
    acwr: float,
    z2_pct: float,
    hr_drift_pct: float,
    decoupling_pct: float,
    next_action: str,
    deep_dive_url: str,
    feedback_url: str,                    # NEW — required
    nutrition_protocol: str = "",
    vmm_projection: str = "",
) -> str:
```

**Output template (Grouped):**

```
⚡ TSS {tss:.0f}  ·  ACWR {acwr:.2f} {zone}
   Z2 {z2_pct:.0f}%  ·  HR drift {hr_drift_pct:.1f}%  ·  Decoupling {decoupling_pct:.1f}%

🍜 Fuel: {nutrition_protocol}          # only if non-empty
🏔️ VMM: {vmm_projection}               # only if non-empty

→ Next: {next_action}                   # only if non-empty

─────────────────
📊 Deep dive:  {deep_dive_url}
💬 Feedback:   {feedback_url}
```

Rules:

- Blank line separates each group (metrics / coaching / next / links).
- If both `nutrition_protocol` and `vmm_projection` are empty, the entire coaching group (including the blank line preceding it) is omitted — do not emit two consecutive blank lines.
- If `next_action` is empty, the `→ Next` line is omitted.
- The divider line is exactly 17 `─` characters.
- The `Deep dive:` / `Feedback:` labels are aligned with two trailing spaces so that on monospace fallbacks the URLs line up visually.

**Callers** (update both):

- `backend/app/services/activity_ingestion.py::_push_description`
- `backend/app/services/activity_ingestion.py::push_description_for_activity`

Each call site constructs:

```python
feedback_url = (
    f"{settings.frontend_url}/feedback/{activity.id}"
    f"?athlete_id={activity.athlete_id}"
)
```

---

## Frontend — public Feedback page

### Route

`frontend/src/pages/Feedback.tsx` — registered as `/feedback/:activityId` in `App.tsx`. Route is public (outside any athlete-guard). Reads `athlete_id` from the query string.

### Layout (mobile-first, warm conversational tone)

Tailwind. Page background `bg-stone-50`, content card `bg-white rounded-xl shadow-sm p-6 max-w-md mx-auto` with top margin on mobile.

```
👋  (large emoji)
Debrief này giúp được anh bao nhiêu?
Tụi mình đang học cách viết debrief tốt hơn — mọi góc nhìn đều quý.

[ 👍 ]  [ 👎 ]    ← two large equal-width buttons, selected state with orange border

Chia sẻ thêm (không bắt buộc)
[ textarea, 3 rows, maxLength 2000, placeholder "VD: Next-action không thực tế với lịch của em..." ]

[ Gửi phản hồi ]   ← full-width primary button, disabled until a thumb is selected

Cảm ơn anh — đọc từng chữ.
```

### Hooks — `src/api/client.ts`

```ts
useExistingFeedback(activityId: number)
  → GET /feedback/activity/:activityId?athlete_id=<id>

useSubmitFeedback()
  → POST /feedback
```

Use the existing `axios` instance + TanStack Query `useQuery` / `useMutation` conventions in the file.

### State machine

- `idle` — form visible. Submit disabled until a thumb is chosen.
- `submitting` — submit button shows spinner, form inputs disabled.
- `submitted` — replaces the card with a confirmation block: "Nhận rồi — cảm ơn anh!" + a "Quay lại Strava" button that opens `strava://activities/<strava_activity_id>` (from the GET response), falling back to `https://www.strava.com/activities/<id>`.
- `error` — inline red toast below the submit button; submit button re-enabled for retry.

On mount, if `useExistingFeedback` returns a non-null `existing`, render the `submitted` state directly (so reloading the page does not invite duplicate submits, though duplicates are allowed server-side).

### Validation (frontend)

- Thumb must be selected.
- Comment `maxLength={2000}` on the textarea.
- If `athlete_id` is missing from the query string, redirect to `/`.

### Types — `src/types/index.ts`

```ts
export type FeedbackThumb = "up" | "down"

export interface FeedbackRequest {
  activity_id: number
  athlete_id: number
  thumb: FeedbackThumb
  comment?: string
}

export interface FeedbackItem {
  id: number
  thumb: FeedbackThumb
  comment: string | null
  created_at: string
}

export interface ExistingFeedbackResponse {
  existing: FeedbackItem | null
  strava_activity_id: number
}
```

---

## Frontend — Admin feedback list

### Route

`frontend/src/admin/pages/Feedback.tsx` registered in `AdminApp.tsx` at `/admin/feedback`, protected by the existing `RequireAdmin` wrapper.

### Nav

`frontend/src/admin/components/AdminNav.tsx` gets a new "Feedback" link. A badge after the label shows `counts.unread` when > 0.

### Layout

```
Phản hồi từ runner

[ Tất cả 24 ]  [ 👎 8 ]  [ 👍 16 ]  [ Chưa đọc 5 ]    ← chips; clicking sets the filter

┌─────────────────────────────────────────────────────────┐
│ 👎  duncan · Run 15km · 2h trước       [• unread]       │
│                                     Mở activity →       │
│ Next-action bảo 90' trail nhưng tuần này em đi          │
│ công tác, không khả thi.                                │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ 👍  mai · Trail 22km · 5h trước                         │
│                                     Mở activity →       │
│ (không có comment)                                      │
└─────────────────────────────────────────────────────────┘

[ Tải thêm ]   ← only when next_cursor !== null
```

Interactions:

- Clicking a card (anywhere except "Mở activity") triggers `PATCH /admin/feedback/:id/read` optimistically and removes the unread dot.
- "Mở activity →" opens `/activities/<activity_id>?athlete_id=<athlete_id>` in a new tab.
- Loading shows 3 skeleton cards. Empty state: "Chưa có phản hồi nào."
- Network error: red banner with a "Tải lại" button.

### Data

`frontend/src/admin/api.ts` gets three new hooks:

```ts
useAdminFeedback(filter, cursor?)
  → GET /admin/feedback
  → useInfiniteQuery, getNextPageParam = (last) => last.next_cursor

useAdminFeedbackCounts()
  → GET /admin/feedback/counts
  → staleTime: 30_000

useMarkFeedbackRead()
  → PATCH /admin/feedback/:id/read
  → onMutate: optimistically patch cached item's read_at
```

### Types — `frontend/src/admin/types.ts`

```ts
export interface AdminFeedbackItem {
  id: number
  thumb: "up" | "down"
  comment: string | null
  created_at: string
  read_at: string | null
  activity_id: number
  activity_name: string
  athlete_id: number
  athlete_name: string
}

export interface AdminFeedbackPage {
  items: AdminFeedbackItem[]
  next_cursor: number | null
}

export interface AdminFeedbackCounts {
  all: number
  up: number
  down: number
  unread: number
}
```

---

## Error handling

- Backend: mismatch between `activity_id` and `athlete_id` always returns `404` — never reveal that the activity exists under a different athlete.
- Backend: the existing `try/except logger.warning(...)` around `_push_description` stays in place; a failed Strava update must never fail activity ingestion.
- Frontend Feedback page: submit failure → visible error; submit re-enabled. Never auto-retry (user-initiated only).
- Frontend admin list: query failure → banner with reload; list does not swallow errors silently.

---

## Rollout

- Single PR targeting `main` from a new branch `feat/user-feedback`.
- No feature flag. Feature is self-contained; new URLs do not affect existing flows.
- Deploy order: migration `003` → backend → frontend. During the rolling window, a user clicking a feedback link on a runner's phone may briefly see a 404 until the frontend rolls. Acceptable for MVP.
- After deploy, ingest one activity manually and verify: new description format appears on Strava, the feedback link opens the mobile page, submit round-trips, admin list shows the row.

---

## Out-of-scope (recorded for future work)

- Signed-token feedback links (add HMAC param if spam appears).
- `debrief_run_id` FK column on `user_feedback` for tight prompt-version correlation.
- Admin reply / conversation thread.
- CSV export of feedback.
- Email/Telegram notification to admin when `👎` comes in.
