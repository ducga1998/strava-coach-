# Richer Recent Activities Rows — Design

**Date:** 2026-04-23
**Status:** Design — executing directly per user instruction
**Owner:** duncan

## Problem

The Recent activities section on the dashboard is sparse. Each row shows only
`name / sport · km · duration | status`. Fields already collected by the
ingestion pipeline (date, elevation gain, hrTSS, zone distribution) are
invisible on the list, so a runner has to click into each activity just to
see whether it was an easy run or a hard session.

## Goal

Make each row information-dense without changing layout style (still a list,
not cards). A glance should tell the user: when, how much, how hard.

## Non-goals

- No card grid, no mini zone bar chart, no plan-compliance chip (reserved for
  a later iteration).
- No change to the activity detail page.
- No pagination / filtering controls.

## Target row layout

```
Apr 20 · Morning run · Run                       [Tempo] 78 TSS
12.4 km · 620 m D+ · 1h 08m                                done
```

- Line 1: `date · name · sport` on the left; `effort badge` + `hrTSS` on the
  right. `hrTSS` is plain text (`78 TSS`). Missing hrTSS → hide the pill.
- Line 2: `km · D+ · duration` on the left; `processing_status` on the right
  (smaller, muted — kept for debugging visibility).
- Rows with no metrics yet (processing / failed) skip the badge and hrTSS
  entirely; status stays.

## Effort classification

Computed server-side in a pure helper:

```python
def _classify_effort(zones: dict[str, float] | None) -> Literal["easy","tempo","hard"] | None:
    if not zones:
        return None
    hard = zones.get("z4_pct", 0.0) + zones.get("z5_pct", 0.0)
    if hard >= 20.0:
        return "hard"
    if zones.get("z3_pct", 0.0) >= 20.0:
        return "tempo"
    return "easy"
```

Thresholds match the coaching philosophy: ≥20% in Z4+Z5 is a real intensity
block; ≥20% in Z3 is a tempo workout; everything else is easy. No metrics →
`None` (client omits the badge).

## Backend

**File:** `backend/app/routers/activities.py`

- Extend `ActivityListOut`:

  ```python
  hr_tss: float | None = None
  effort: Literal["easy", "tempo", "hard"] | None = None
  ```

- Rewrite `list_activities` to `LEFT OUTER JOIN` `ActivityMetrics` in a
  single query so we don't pay N+1 for 50 rows:

  ```python
  stmt = (
      select(Activity, ActivityMetrics)
      .outerjoin(ActivityMetrics, ActivityMetrics.activity_id == Activity.id)
      .where(Activity.athlete_id == athlete_id)
      .order_by(Activity.start_date.desc())
      .limit(50)
  )
  result = await db.execute(stmt)
  return [_list_out(activity, metrics) for activity, metrics in result.all()]
  ```

- New private helper `_list_out(activity, metrics)` builds the response with
  `hr_tss` and `effort` populated from the metrics row (or `None`).

- `_classify_effort` lives in the same module as a pure function (easy to
  unit-test).

## Frontend

**Files:**
- `frontend/src/types/index.ts` — `ActivityListItem` gains:
  ```ts
  hr_tss: number | null
  effort: "easy" | "tempo" | "hard" | null
  ```
- `frontend/src/pages/Dashboard.tsx` — rewrite `ActivityRow` to the
  two-line layout above. Effort badge is a small Tailwind pill:
  - `easy` → emerald
  - `tempo` → amber
  - `hard` → red
  Status badge stays but drops to a smaller / more muted treatment so the
  effort badge carries the primary visual weight.

Small date formatter (`MMM DD`, e.g. `Apr 20`) added alongside the existing
`formatKm` / `formatMinutes` helpers in the Dashboard file.

## Testing

- Backend: 4 unit tests for `_classify_effort` (easy / tempo / hard /
  None-when-missing).
- Backend: integration test — `GET /activities/?athlete_id=` returns the new
  fields, with the correct `effort` for a seeded metrics row and `None` for
  an activity without metrics.
- Frontend: `npm run typecheck` + `npm run build`.

## Out of scope (explicit)

- Mini zone-distribution bar per row.
- Debrief teaser text.
- Plan-compliance score chip.
- Grouping by week.
- Server-side filtering or pagination.

Any of these can be added in a follow-up spec once the simpler richer-row
design is in the user's hands.
