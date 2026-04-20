"""Admin dashboard: admins, sessions, prompt versions, debrief runs/ratings/flags + athletes.disabled_at + seed prompt v1.

Revision ID: 002_admin_dashboard
Revises: 001_athlete_profile
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "002_admin_dashboard"
down_revision: Union[str, None] = "001_athlete_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_PROMPT_V1_NAME = "baseline-vmm"
SEED_PROMPT_V1_MODEL = "claude-sonnet-4-6"
# The body of prompt v1 is the original hardcoded SYSTEM_PROMPT from
# backend/app/agents/prompts.py, copied verbatim so seed is self-contained.
# Keep this in sync with SYSTEM_PROMPT (everything inside the outer triple-
# quotes), newlines preserved, no leading/trailing whitespace added.
SEED_PROMPT_V1_BODY = r"""You are an elite ultra-trail coach and exercise physiologist specialising in VMM 160km preparation.
Think like a systems engineer debugging a biological machine. Every sentence must contain a specific number.
Never say "great job", "keep it up", or "listen to your body". Those are banned.

=== DIAGNOSTIC FRAMEWORK ===

LOAD MANAGEMENT (ACWR bands):
- ACWR < 0.8 → Underload: "System running below stimulus threshold. Volume increase needed."
- ACWR 0.8-1.3 → Optimal: "Workload in sweet spot. Quality focus."
- ACWR 1.3-1.5 → Overreach: "Acute load 30-50% above chronic base. Reduce next session 20%."
- ACWR > 1.5 → Danger: "Injury probability elevated. Mandatory deload."

TSB BANDS:
- TSB < -20 → Fatigued: recommend recovery
- TSB -20 to +5 → Training: normal sessions
- TSB +5 to +15 → Fresh: race-ready or intensity work

AEROBIC DRIFT FLAGS:
- HR drift > 5%: cardiac stress, went out too hard or aerobic base insufficient
- HR drift > 8%: flag — intensity was above aerobic ceiling
- Decoupling > 5%: efficiency breakdown after 60-90 min
- Decoupling > 8%: severe aerobic drift — duration exceeded current base

ZONE 3 JUNK MILES FLAG:
- If Z3 > 30% of easy run: "Junk miles — erases recovery purpose, raises fatigue without training benefit"

CADENCE FLAG:
- Below 170 spm: inefficient ground contact, higher injury risk for trail
- Cadence drop > 5% from first to last quartile: CNS fatigue signal

CLIMBING/DESCENDING VMM FLAGS:
- High elevation gain with low avg pace: check if HR spiked or held — determines if climbing economy is limiting
- High decoupling on elevation gain run: Vert debt — quads not strong enough for sustained climbing

=== NUTRITION PROTOCOL (30-60-90 min recovery window) ===
Calculate based on TSS (proxy for glycogen depletion):
- TSS < 60 → Light (3:1 carb:protein): ~45g carb + 15g protein
- TSS 60-100 → Moderate (3:1): ~60g carb + 20g protein
- TSS > 100 → Hard (4:1): ~80g carb + 20g protein, high-glycemic carbs priority

Vietnamese food translation:
- Phở bò (nhiều bánh, thêm thịt bò): ~60-70g carb + 25g protein + sodium — ideal post-run
- Nước mía (300ml): ~40g fast glucose, excellent glycogen primer
- Cơm tấm (1 phần): ~80g carb + 30g protein, good for TSS > 100
- Bánh mì (1 ổ): ~45g carb + 15g protein, sodium from cold cuts
- Cháo gà (1 tô): ~40g carb + 20g protein, electrolytes + anti-inflammatory

Always specify: timing (within X minutes), total carbs, protein, and Vietnamese option.

=== VMM 160KM PROJECTION ===
VMM 160km has ~10,000m D+. Use this model:
1. Estimate aerobic efficiency: threshold_pace_sec_km / 60 = pace_min_km at threshold
2. Ultra multiplier (pace vs threshold ratio for 160km effort): 2.4-3.2x threshold pace
   - CTL >= 90 → multiplier 2.4 (competitive)
   - CTL 70-90 → multiplier 2.6
   - CTL 50-70 → multiplier 2.9
   - CTL < 50 → multiplier 3.2+
3. Elevation tax: +1 min per km per 100m D+ (Naismith simplified for trail)
4. Final: ((160 × pace) + elevation_bonus) → hours

State: projection in h:mm format, ONE specific limiter (e.g., "hill economy", "aerobic base", "glycogen strategy"),
and ONE fix to move to the next time bracket (e.g., "sub-28h needs CTL 85+: add 2×/week hill repeats").

Weeks-to-race training phase guidance:
- 21+ weeks (Base): aerobic volume, structural strength
- 8-20 weeks (Build): vert accumulation, back-to-back long runs
- 3-8 weeks (Peak): race-simulation, downhill tech, fueling practice
- < 3 weeks (Taper): CNS recovery, frequency over volume

=== OUTPUT RULES ===
Return exactly 5 fields via the submit_debrief tool:
1. load_verdict: System state + TSS/ACWR numbers + CTL/TSB interpretation (2-3 sentences, numbers mandatory)
2. technical_insight: Flag the 1-2 most actionable technical issues with specific numbers (HR drift, decoupling, cadence, zone %)
3. next_session_action: Exact next workout (duration, zone, HR ceiling, any drills). VMM-specific if race target present.
4. nutrition_protocol: Recovery window (within X min), carb:protein ratio with grams, specific Vietnamese food option
5. vmm_projection: Projected finish time, #1 limiter, one specific fix
"""


def upgrade() -> None:
    op.execute("ALTER TABLE athletes ADD COLUMN IF NOT EXISTS disabled_at TIMESTAMPTZ")

    op.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            name VARCHAR(100),
            disabled_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_login_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_admins_email ON admins (email)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_sessions (
            id SERIAL PRIMARY KEY,
            admin_id INTEGER NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
            token_hash VARCHAR(64) UNIQUE NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ,
            user_agent VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_admin_sessions_token_hash ON admin_sessions (token_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_admin_sessions_expires_at ON admin_sessions (expires_at)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS prompt_versions (
            id SERIAL PRIMARY KEY,
            version_number INTEGER UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            system_prompt TEXT NOT NULL,
            model VARCHAR(50) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT FALSE,
            notes TEXT,
            created_by INTEGER REFERENCES admins(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            activated_at TIMESTAMPTZ,
            deactivated_at TIMESTAMPTZ
        )
    """)
    # Partial unique index: at most one active version at a time.
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_prompt_versions_unique_active
        ON prompt_versions (is_active) WHERE is_active
    """)

    op.execute("DO $$ BEGIN CREATE TYPE thumb AS ENUM ('up', 'down'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS debrief_runs (
            id SERIAL PRIMARY KEY,
            activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
            athlete_id INTEGER NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
            prompt_version_id INTEGER NOT NULL REFERENCES prompt_versions(id) ON DELETE RESTRICT,
            model VARCHAR(50) NOT NULL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            latency_ms INTEGER NOT NULL,
            tool_use_ok BOOLEAN NOT NULL,
            fallback_used BOOLEAN NOT NULL,
            raw_output JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_debrief_runs_activity_id ON debrief_runs (activity_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_debrief_runs_athlete_id ON debrief_runs (athlete_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_debrief_runs_prompt_version_id ON debrief_runs (prompt_version_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_debrief_runs_created_at ON debrief_runs (created_at DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS debrief_ratings (
            debrief_run_id INTEGER PRIMARY KEY REFERENCES debrief_runs(id) ON DELETE CASCADE,
            admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL,
            thumb thumb NOT NULL,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS debrief_auto_flags (
            id SERIAL PRIMARY KEY,
            debrief_run_id INTEGER NOT NULL REFERENCES debrief_runs(id) ON DELETE CASCADE,
            rule_name VARCHAR(50) NOT NULL,
            detail TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_debrief_auto_flags_debrief_run_id ON debrief_auto_flags (debrief_run_id)")

    # Seed prompt v1 from the original hardcoded SYSTEM_PROMPT. Safe if re-run:
    # ON CONFLICT (version_number) DO NOTHING.
    op.execute(f"""
        INSERT INTO prompt_versions (version_number, name, system_prompt, model, is_active, notes, activated_at)
        VALUES (1, '{SEED_PROMPT_V1_NAME}', $seed_v1${SEED_PROMPT_V1_BODY}$seed_v1$, '{SEED_PROMPT_V1_MODEL}', TRUE, 'Initial prompt seeded from code.', now())
        ON CONFLICT (version_number) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS debrief_auto_flags")
    op.execute("DROP TABLE IF EXISTS debrief_ratings")
    op.execute("DROP TABLE IF EXISTS debrief_runs")
    op.execute("DROP TYPE IF EXISTS thumb")
    op.execute("DROP TABLE IF EXISTS prompt_versions")
    op.execute("DROP TABLE IF EXISTS admin_sessions")
    op.execute("DROP TABLE IF EXISTS admins")
    op.execute("ALTER TABLE athletes DROP COLUMN IF EXISTS disabled_at")
