PRD — Strava AI Coach (codename: TBD)
Vision: Post-run AI debrief + readiness score for ultra/trail runners, starting with SEA market. Not another generic Strava wrapper — numeric, actionable, coach-quality output.
Primary persona: Ultra/trail runner, 30-45, self-coached, Strava+Garmin user, training for specific race (VMM, UTMB, UTSN, DCR). Pain: Strava shows data, doesn't interpret. TrainingPeaks overkill + $20/mo. Runna is road-only.
Success metric (North Star): % of post-run debriefs read within 24h × weekly active athletes. Target: >60% × 70% WAU at month 3 of beta.

User Stories & Acceptance Criteria
US-01 — Strava OAuth Connection
As an athlete, I want to connect my Strava account in one click so that my activities flow in automatically.
AC:

Given I'm on the landing page, When I click "Connect Strava", Then I'm redirected to Strava OAuth consent with scopes read,activity:read_all,profile:read_all.
Given I approve, When redirected back, Then my athlete_id, access_token, refresh_token, expires_at are stored encrypted (AES-256) in strava_credentials.
Given token expires, When any API call is made, Then refresh flow executes transparently; user never sees re-login unless refresh fails 3 times consecutively.
Given I disconnect, When I click "Revoke", Then webhook subscription is cancelled via DELETE /push_subscriptions/:id, tokens are deleted, and historical computed metrics are retained but flagged source_disconnected=true.

Edge cases: Strava rate limit hit (429) → exponential backoff + user notified only if >6h delay. OAuth state CSRF token validated.

US-02 — Athlete Baseline Setup
As an athlete, I want to configure my physiological thresholds and preferences so that metrics are personalized, not generic zone 1-5 garbage.
AC:

Given I finish OAuth, When onboarding loads, Then I see a 4-step wizard: (1) Threshold HR (LTHR) + max HR, (2) Threshold pace / critical velocity (flat), (3) Body metrics (weight, optional VO2max estimate), (4) Preferred units (metric/imperial) and language (EN/VN).
Given I have 30+ days of Strava history, When I land on step 1, Then system auto-suggests LTHR from 20-min max HR segments in recent activities (highlight the source activity).
Given I skip onboarding, When I access dashboard, Then metrics fall back to Karvonen zones with explicit banner "Personalize for better accuracy".
Given I save, When I re-open settings, Then all values persist with "last updated" timestamp. Recomputation of historical metrics triggers async job, completes <5min for 12 months of data.


US-03 — Training Target Configuration
As an athlete training for a specific race, I want to define my target race so that coaching output is contextual to my A-race, not generic fitness.
AC:

Given I'm in "Targets" section, When I add a target, Then I input: race name, date, distance (km), elevation gain (m), goal time (optional), priority (A/B/C).
Given race date is set, When dashboard renders, Then a countdown + current phase (Base/Build/Peak/Taper — computed from weeks-to-race) is shown.
Given multiple A-races exist, When I view plan, Then the nearest A-race drives coaching context; others listed as "upcoming".
Given race is past, When 14 days elapse, Then system prompts "Rate this race + add next target".


US-04 — Activity Auto-Ingestion
As an athlete, I want new activities to be processed automatically so that I don't trigger anything manually.
AC:

Given a Strava webhook fires aspect_type=create, object_type=activity, When received at POST /webhook/strava, Then payload is validated (HMAC verify_token), enqueued to Cloudflare Queue, and 200 returned <500ms.
Given activity is queued, When worker picks it up, Then it fetches /activities/{id} + streams [heartrate, altitude, velocity_smooth, time, latlng, cadence, watts] and persists raw streams (gzipped JSONB) + activity metadata.
Given activity type is running/trail running/hiking, When ingested, Then metrics engine runs: TSS, hrTSS, GAP, NGP, HR drift, aerobic decoupling, ACWR update, CTL/ATL/TSB update.
Given activity type is outside supported list (swim, ride — MVP excluded), When ingested, Then raw data stored but no metrics computed; tagged skipped_reason.
Given activity is <10 min or <1km, When processed, Then flagged excluded_from_load=true (avoid warmup noise polluting CTL).
Given processing fails, When retry count <3, Then exponential backoff (1min, 5min, 30min); after 3 failures → dead letter queue + Sentry alert.

SLA: 95% of activities processed + debrief ready within 10 minutes of Strava sync.

US-05 — Post-Run Debrief
As an athlete, I want a short, specific AI debrief after each run so that I understand what happened and what to do next.
AC:

Given metrics computation completes, When debrief generator runs, Then LLM is called with structured input: {activity_metrics, athlete_profile, recent_load_7d, target_context, training_phase} and constrained output schema (3 sections, max 400 chars each).
Given LLM returns, When rendered, Then debrief contains exactly: (1) Load verdict — numeric (TSS vs 30d avg %, ACWR value + zone), (2) Technical insight — one finding (HR drift %, pace decoupling, GAP vs expected, zone distribution anomaly), (3) Next-session actionable — specific (not "rest well").
Given debrief is ready, When user has push enabled, Then push notification fires within 10min of activity sync.
Given athlete opens debrief, When rendered, Then each claim links to source metric (click "HR drift 7.2%" → see Pa:HR chart).
Given LLM output violates schema (too long, missing section, hallucinated metric), When validator fails, Then retry once; if still fails → fallback to deterministic template. Log to eval dataset.

Quality bar: No generic phrases ("great job", "keep it up", "listen to your body"). Every claim has a number. Enforced via LLM-as-judge eval on release.

US-06 — Training Load Dashboard
As an athlete, I want to see my current load state so that I can decide whether to push or rest.
AC:

Given I open dashboard, When rendered, Then I see: CTL/ATL/TSB line chart (90d), ACWR gauge with zones (green 0.8-1.3, yellow 1.3-1.5, red >1.5), weekly volume (km + D+), current training phase.
Given ACWR >1.5 or TSB <-30, When dashboard loads, Then warning banner: "Injury risk zone — consider deload".
Given I have <14d of data, When dashboard loads, Then metrics shown as "baselining" with ETA to full accuracy.


US-07 — Weekly Readiness Score (Phase 3+)
As an athlete, I want a weekly go/caution/rest score so that I plan the upcoming week with confidence.
AC:

Given it's Sunday 18:00 local time, When weekly job runs, Then score (0-100) is computed from: TSB, ACWR, monotony, strain, HRV trend (if connected), sleep trend (if connected).
Given score is ready, When I open app, Then I see score + 1-paragraph AI summary of the week + recommended load for next week (±% of last week).


Phase Breakdown
Total MVP timeline: 8-10 weeks solo, dogfooding from week 3.
Phase 0 — Infra & Strava Integration (Week 1-2)
Scope:

Repo setup (monorepo: apps/web, apps/worker, packages/metrics, packages/strava-client)
Stack: Fastify + PostgreSQL + Cloudflare Workers (webhook ingress) + Cloudflare Queue + Next.js frontend
Strava OAuth flow + token refresh + encrypted storage
Webhook subscription + HMAC validation + event queue
Basic /activities/{id} + streams fetch with rate-limit-aware client

Deliverables:

User can connect Strava, new activity lands in DB within 60s, raw streams stored
Integration tests against Strava sandbox
Strava production API application submitted

Exit criteria:

Dogfood: my own Strava account ingesting reliably for 7d with zero missed activities


Phase 1 — Metrics Engine (Week 2-4, parallel with Phase 0)
Scope:

Pure-function metrics library (packages/metrics): TSS, hrTSS, GAP, NGP, CTL, ATL, TSB, ACWR, monotony, strain, HR drift, aerobic decoupling
Backfill job: compute metrics for last 12 months per user
Validation harness: cross-check every metric against Intervals.icu for the same activity, tolerance ±5%

Deliverables:

100% unit test coverage on metrics package
Validation report: my own 12-month data, metric-by-metric vs Intervals.icu

Exit criteria:

Metric deltas vs Intervals.icu <5% median, <10% p95. If any metric fails → don't ship that metric, drop it from v1.


Phase 2 — Onboarding & Targets (Week 4-5)
Scope:

4-step wizard UI (LTHR, thresholds, body, preferences)
LTHR auto-detection from history
Target race CRUD
Training phase auto-computation (Base/Build/Peak/Taper based on weeks-to-A-race and classic periodization rules)

Deliverables:

Working onboarding at /setup
Settings page to edit thresholds post-onboarding
Targets page with race countdown

Exit criteria:

3 alpha testers (from VMM community) complete onboarding without support


Phase 3 — AI Coaching Layer (Week 5-7)
Scope:

Prompt engineering: system prompt with coaching framework (Friel periodization, Magness physiological cues, Koerner ultra-specific)
Structured input schema: all metrics + profile + phase + recent load + target
Output schema enforced via JSON mode (Claude Sonnet 4 or GPT-4o — benchmark both)
Golden dataset: 20 hand-written debriefs from my own activities (I already have the plan + activities → write ideal output manually)
LLM-as-judge eval harness: each release scored against golden set on (specificity, actionability, numeric grounding, no-fluff)
Fallback: deterministic template if LLM fails schema

Deliverables:

Debrief generator service
Eval dashboard (scores per release)

Exit criteria:

Eval score >4/5 on golden set
Manual review of 20 debriefs on fresh activities: zero hallucinated metrics, zero generic phrases


Phase 4 — Delivery Layer (Week 7-8)
Scope:

Dashboard (load chart, ACWR gauge, phase indicator)
Activity detail page with debrief + metric deep-dive
Push notifications (Web Push + optional Telegram bot for VN users)
Email digest (optional)

Deliverables:

End-to-end: new run in Strava → debrief in app + push within 10min

Exit criteria:

Lighthouse >90 on mobile
E2E test: ride new Strava activity → assert debrief delivered within SLA


Phase 5 — Private Beta (Week 8+)
Scope:

Invite 8-12 runners (VMM 100/160 cohort, known to me)
Weekly feedback form + 1:1 call at week 2 and week 4
Instrument: debrief open rate, push CTR, 7d retention, NPS, qualitative "would you pay" signal
Ship readiness score (US-07) during beta based on signal

Exit criteria to public beta:

60% of active athletes open >70% of debriefs
NPS >40
At least 3 testers explicitly say "I'd pay $X/month"
Zero P0 bugs for 14 consecutive days


Risks Register
RiskSeverityMitigationStrava revokes API access (ToS tightening, 2023-2024 precedent)CriticalBuild Garmin Connect + FIT file upload fallback from Phase 1; never store raw Strava data in a way that requires Strava for replayMetric computation wrong → bad coaching → injuryHighIntervals.icu validation gate; disclaimer; conservative thresholds in warning logicLLM cost scales with usersMediumCache deterministic parts of prompt; use Haiku for first-pass, Sonnet only for nuanced cases; budget $0.20/athlete/month capLLM hallucination on metricsHighStructured output + schema validation + LLM-as-judge eval on every releaseSolo build = bus factor 1MediumHeavy test coverage, clear docs, scoped MVPCompetition (Strava Athlete Intelligence, Runna expansion)MediumNarrow ICP: ultra/trail SEA. Ship Vietnamese language + local race calendar as defensible wedge

Out of Scope for MVP (Parking Lot)

Custom training plan generation (v2 — big LLM eval problem)
Strength/cross-training recommendations
Nutrition/fueling (liability risk, separate compliance)
Human coach marketplace (v2, B2B2C)
iOS/Android native apps (PWA first)
Ride/swim/triathlon (v2, different metrics)
HRV/sleep integrations (Phase 5 if signal strong)
