# Debrief Language Toggle (EN / VI) — Design

**Date:** 2026-04-22
**Status:** Design — pending implementation plan
**Owner:** duncan

---

## Problem

The AI debrief is the core differentiator of the product. Currently every debrief is produced in English, regardless of the athlete's `language` field (which is already collected during onboarding and stored in `Athlete.language`). A Vietnamese ultra runner reading daily coaching analysis gets English prose that reads less personally than their native language would.

There is also no post-onboarding way to change the language — the field is write-once via `POST /onboarding/profile`.

## Goal

Allow the user to switch their AI debrief output between English and Vietnamese from anywhere in the app. UI chrome stays in English.

## Non-goals

- Translating UI labels, chart titles, metric names, or navigation.
- Retroactively regenerating existing debriefs. Once a debrief is written to the DB it stays in its original language.
- Supporting additional languages beyond `en` and `vi`.
- Per-activity language override.

## Design

### 1. UI — `LanguagePicker` in the app header

A compact dropdown lives in `frontend/src/components/layout/AppChromeHeader.tsx` next to existing header content. It only renders when `getStoredAthleteId()` is non-null (same gating pattern as `PushDescriptionButton` after the 2026-04-22 fix).

**Closed state:** `EN ▾` or `VI ▾` (shows the currently saved value).
**Open state:** two options — `English` and `Tiếng Việt`.
**On select:**
1. Optimistically update local cached athlete profile.
2. Call `PATCH /athletes/{id}/language` with `{ language: "en" | "vi" }`.
3. Invalidate the `["athlete", athleteId]` query so any page reading `profile.language` refreshes.
4. Show a short toast: `"Saved — future debriefs will be in Vietnamese"` (or English). Existing debriefs keep their original language.
5. On API failure: revert optimistic state and surface an error toast.

Current language is read from `athleteQuery.data.profile.language`. No new `language` field is added to `localStorage` — the server is the source of truth.

### 2. Backend — `PATCH /athletes/{id}/language`

New endpoint in `backend/app/routers/athletes.py` (or the existing athletes router — whichever is already handling `GET /athletes/{id}`).

```python
class LanguageUpdate(BaseModel):
    language: Literal["en", "vi"]

@router.patch("/{athlete_id}/language", response_model=ProfileOut)
async def update_language(
    athlete_id: int,
    payload: LanguageUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    ...
```

Why a new endpoint rather than reusing `POST /onboarding/profile`:
- `POST /onboarding/profile` expects a full onboarding payload (lthr, max_hr, threshold pace, weight, vo2max, units, language). Requiring the client to re-send all of that to toggle one field is wrong.
- The onboarding endpoint also flips `onboarding_complete = True` as a side effect; the language toggle should not touch that flag.

The `Literal["en", "vi"]` on the Pydantic model enforces the two-value constraint at the API boundary. Unknown values return 422.

### 3. Debrief prompt — honor `language`

**`backend/app/agents/prompts.py`**

`build_debrief_prompt(activity, context, language="en")` gains a third parameter. When `language == "vi"`, append the following block to the end of the prompt (after all instrumentation and diagnostic sections, before the LLM generates):

```
=== LANGUAGE ===
Respond entirely in Vietnamese. All narrative fields (summary, workout_assessment,
recovery_guidance, plan_compliance, next_session_recommendation) must be natural
Vietnamese prose. Keep metric names, numbers, and units (hrTSS, ACWR, TSB, CTL,
ATL, bpm, km, min/km, %, spm) unchanged — do not translate them.
```

For `language == "en"`, no extra block is appended (current behavior).

**`backend/app/agents/debrief_graph.py`**

The graph node that reads the athlete profile already has access to `Athlete.language`. Pass it through to `build_debrief_prompt` and also to `fallback_debrief`.

**Rule-based fallback (`fallback_debrief`) — out of scope for this iteration**

The fallback is built from five helper functions (`_load_verdict`, `_technical_insight`, `_next_session_action`, `_nutrition_protocol`, `_vmm_projection`) each producing branching English prose. Fully translating them would roughly double the module size and is disproportionate for a rarely-hit path (fallback only fires when the Anthropic call errors).

For this iteration the fallback continues to emit English regardless of `language`. The `_nutrition_protocol` helper is already partially Vietnamese (Phở, Bánh mì). If a Vietnamese athlete hits the fallback path they will see a mixed-language debrief — acceptable trade-off for MVP.

A follow-up spec can introduce a phrase table per band if the fallback proves to be a meaningful share of production debriefs.

### 4. Data flow

```
User clicks EN/VI in header
  → PATCH /athletes/{id}/language { language: "vi" }
    → Athlete.language updated in DB
  → query invalidate → athlete profile re-fetched
  → toast: "Saved"

Later: new activity ingested
  → webhook fires → activity processed → debrief_graph runs
    → reads Athlete.language = "vi"
    → build_debrief_prompt(..., language="vi") → LLM responds in Vietnamese
    → DebriefOutput fields are Vietnamese prose
  → stored in DB as-is
  → frontend renders the Vietnamese strings unchanged
```

Existing debriefs in the DB are untouched.

### 5. Testing

**Backend**
- `test_prompts.py`: assert `build_debrief_prompt(..., language="vi")` contains `"Respond entirely in Vietnamese"` and `build_debrief_prompt(..., language="en")` does not.
- `test_fallback.py`: assert `fallback_debrief(..., language="vi")` returns a `DebriefOutput` whose `summary` matches a Vietnamese phrase from the table.
- `test_athletes_router.py`: assert `PATCH /athletes/{id}/language` with `{"language": "vi"}` updates the row and returns updated profile. Assert `{"language": "fr"}` returns 422. Assert `onboarding_complete` is not flipped by the call.

**Frontend**
- `npm run typecheck` — no type regressions.
- Manual smoke: open dashboard, toggle VI, reload, confirm dropdown persists as VI, trigger a new debrief, confirm it is Vietnamese.

No Playwright test added — the flow is small and the language-picker UX is a simple dropdown.

### 6. Scope boundaries (what we are NOT doing)

- No UI string translation.
- No retroactive regeneration of existing debriefs. If the user wants Vietnamese versions of past debriefs, that is a separate feature (`POST /activities/{id}/regenerate-debrief`) and not in this scope.
- No automatic browser-language detection. User explicitly picks.
- No per-athlete language inheritance from Strava profile — user chose at onboarding, can change in header.

## Files touched (preview — exact list lives in the implementation plan)

Backend:
- `backend/app/agents/prompts.py` — add `language` parameter, append Vietnamese instruction block.
- `backend/app/agents/schema.py` — add `language: Literal["en", "vi"]` to `AthleteContext`.
- `backend/app/agents/debrief_graph.py` — pass `language` to `build_debrief_prompt`.
- `backend/app/services/activity_ingestion.py` — populate `AthleteContext.language` from `AthleteProfile.language`.
- `backend/app/routers/athletes.py` — new `PATCH /{athlete_id}/language` endpoint; expose `language` in `AthleteProfileOut`.
- `backend/tests/test_agents/test_prompts.py` — language branch tests.
- `backend/tests/test_routers/test_athletes.py` — PATCH endpoint tests + `language` in GET response.

Frontend:
- `frontend/src/components/layout/LanguagePicker.tsx` — new component.
- `frontend/src/components/layout/AppChromeHeader.tsx` — mount `LanguagePicker`.
- `frontend/src/api/client.ts` — `updateAthleteLanguage(athleteId, language)` helper.
- `frontend/src/types/index.ts` — already has `LanguageCode` type; confirm it is `"en" | "vi"`.

## Risks

- **LLM compliance:** Claude Sonnet 4.6 may occasionally mix English technical terms into Vietnamese prose. The prompt explicitly allows metric names/units to stay English, so this is expected and acceptable. Monitor eval output in `docs/superpowers/eval-runs/`.
- **Fallback translation drift:** the rule-based fallback phrase table is hand-maintained. If a new ACWR/TSB band or compliance verdict is added to the English fallback, the Vietnamese table must be updated in the same commit. Add a unit test that asserts both language dicts have the same keys.
- **Existing debrief mixing:** dashboard will show a mix of English and Vietnamese debriefs after a user switches — one Vietnamese debrief next to older English ones. This is the expected behavior; no UI treatment needed.
