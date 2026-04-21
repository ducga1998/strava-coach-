import logging

import anthropic

from app.agents.prompts import SYSTEM_PROMPT, build_debrief_prompt
from app.agents.schema import (
    ActivityInput,
    AthleteContext,
    DebriefOutput,
    PlannedWorkoutContext,
    RaceTargetContext,
)
from app.config import settings
from app.services.description_builder import acwr_zone_label

logger = logging.getLogger(__name__)

GENERIC_PHRASES = ("great job", "keep it up", "listen to your body")

_DEBRIEF_TOOL: anthropic.types.ToolParam = {
    "name": "submit_debrief",
    "description": "Submit physiological debrief with nutrition and VMM projection",
    "input_schema": {
        "type": "object",
        "properties": {
            "load_verdict": {
                "type": "string",
                "description": "System state: TSS vs average, ACWR band, CTL/TSB interpretation (numbers mandatory)",
            },
            "technical_insight": {
                "type": "string",
                "description": "1-2 most actionable technical issues with specific metric values",
            },
            "next_session_action": {
                "type": "string",
                "description": "Exact next workout: duration, zone, HR ceiling, VMM-specific drills if applicable",
            },
            "nutrition_protocol": {
                "type": "string",
                "description": "Recovery: timing window, carb:protein grams, specific Vietnamese food option",
            },
            "vmm_projection": {
                "type": "string",
                "description": "Projected VMM 160km finish time, #1 current limiter, one fix to next bracket",
            },
            "plan_compliance": {
                "type": "string",
                "description": (
                    "Only when the prompt contains === PLANNED WORKOUT (today) ===. "
                    "Start with '<0-100>/100 ' then one sentence. "
                    "Emit empty string if no plan block present."
                ),
            },
        },
        "required": [
            "load_verdict",
            "technical_insight",
            "next_session_action",
            "nutrition_protocol",
            "vmm_projection",
        ],
    },
}


async def generate_debrief(
    activity: ActivityInput, context: AthleteContext
) -> dict[str, str]:
    if settings.enable_llm_debriefs and settings.anthropic_api_key:
        try:
            return await _llm_debrief(activity, context)
        except Exception:
            logger.warning("LLM debrief failed, using rule-based fallback", exc_info=True)
    return fallback_debrief(activity, context).model_dump()


async def _llm_debrief(
    activity: ActivityInput, context: AthleteContext
) -> dict[str, str]:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_prompt = build_debrief_prompt(activity.model_dump(), context.model_dump())

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        tools=[_DEBRIEF_TOOL],
        tool_choice={"type": "tool", "name": "submit_debrief"},
        messages=[{"role": "user", "content": user_prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_debrief":
            result: dict[str, str] = block.input  # type: ignore[assignment]
            combined = " ".join(result.values()).lower()
            if any(phrase in combined for phrase in GENERIC_PHRASES):
                logger.warning("LLM output contained generic phrase — falling back")
                return fallback_debrief(activity, context).model_dump()
            # Back-fill plan_compliance deterministically when the LLM
            # omitted it despite a plan being present. This keeps the
            # frontend badge parser reliable.
            if context.planned_today is not None and not result.get("plan_compliance"):
                result["plan_compliance"] = format_plan_compliance_string(
                    planned=context.planned_today,
                    actual_tss=activity.hr_tss or activity.tss,
                    actual_duration_min=activity.duration_sec / 60,
                    zone_distribution=activity.zone_distribution,
                )
            result.setdefault("plan_compliance", "")
            return result

    return fallback_debrief(activity, context).model_dump()


# ---------------------------------------------------------------------------
# Rule-based fallback — specific and number-backed even without LLM
# ---------------------------------------------------------------------------

def fallback_debrief(activity: ActivityInput, context: AthleteContext) -> DebriefOutput:
    plan_compliance = ""
    if context.planned_today is not None:
        plan_compliance = format_plan_compliance_string(
            planned=context.planned_today,
            actual_tss=activity.hr_tss or activity.tss,
            actual_duration_min=activity.duration_sec / 60,
            zone_distribution=activity.zone_distribution,
        )

    return DebriefOutput(
        load_verdict=_load_verdict(activity, context),
        technical_insight=_technical_insight(activity),
        next_session_action=_next_session_action(context),
        nutrition_protocol=_nutrition_protocol(activity),
        vmm_projection=_vmm_projection(context),
        plan_compliance=plan_compliance,
    )


def _load_verdict(activity: ActivityInput, context: AthleteContext) -> str:
    tss_pct = percent_of_average(activity.tss, context.tss_30d_avg)
    zone = acwr_zone_label(context.acwr)
    tsb_state = (
        "fatigued" if context.tsb < -20
        else "training-fresh" if context.tsb < 5
        else "race-ready"
    )
    return (
        f"TSS {activity.tss:.0f} = {tss_pct:.0f}% of 30-day average ({context.tss_30d_avg:.0f}). "
        f"ACWR {context.acwr:.2f} → {zone}. "
        f"CTL {context.ctl:.0f} / TSB {context.tsb:+.0f} ({tsb_state}). "
        f"ATL {context.atl:.0f} reflects acute load from last 7 days."
    )


def _technical_insight(activity: ActivityInput) -> str:
    parts: list[str] = []
    z2 = activity.zone_distribution.get("z2_pct", 0.0)
    z3 = activity.zone_distribution.get("z3_pct", 0.0)

    if activity.hr_drift_pct > 8:
        parts.append(
            f"HR spiked {activity.hr_drift_pct:.1f}% — pacing exceeded aerobic ceiling; "
            f"cardiac drift signals intensity above sustainable Z2."
        )
    elif activity.hr_drift_pct < -8:
        parts.append(
            f"HR dropped {abs(activity.hr_drift_pct):.1f}% as session progressed — "
            f"classic descent-heavy profile; cardiac efficiency improved with terrain."
        )
    elif abs(activity.hr_drift_pct) > 5:
        parts.append(f"HR drift {activity.hr_drift_pct:.1f}% — borderline; aerobic ceiling approached in final third.")

    if activity.aerobic_decoupling_pct > 8:
        parts.append(
            f"Decoupling {activity.aerobic_decoupling_pct:.1f}% — severe efficiency breakdown. "
            f"Duration exceeded current aerobic base. Build CTL before extending efforts."
        )
    elif activity.aerobic_decoupling_pct > 5:
        parts.append(f"Decoupling {activity.aerobic_decoupling_pct:.1f}% — aerobic base needs 3-4 more weeks at this volume.")

    if z3 > 30:
        parts.append(f"Z3 {z3:.0f}% — junk miles. Erases recovery without building aerobic capacity. Cap at 10% Z3 on easy days.")

    if activity.elevation_gain_m > 500 and activity.aerobic_decoupling_pct > 10:
        parts.append(f"+{activity.elevation_gain_m:.0f}m D+ with {activity.aerobic_decoupling_pct:.0f}% decoupling = vert debt. Climbing economy is limiting performance.")

    if activity.cadence_avg and activity.cadence_avg < 170:
        parts.append(f"Cadence {activity.cadence_avg:.0f} spm — below 170 threshold. Overstriding increases metabolic cost and injury risk.")

    if not parts:
        parts.append(
            f"HR drift {activity.hr_drift_pct:.1f}% and decoupling "
            f"{activity.aerobic_decoupling_pct:.1f}% with Z2 {z2:.0f}%. "
            f"Metrics within normal range."
        )

    return " ".join(parts)


def _next_session_action(context: AthleteContext) -> str:
    target = context.race_target
    prefix = f"{target.race_name} {target.weeks_out}w: " if target else ""

    if context.acwr > 1.5 or context.tsb < -30:
        action = (
            "Recovery run 40-50 min, HR < LTHR-30 bpm, flat terrain only. "
            "Reduce next 3 sessions by 20% volume. Prioritise 8h sleep."
        )
    elif context.acwr > 1.3:
        action = (
            "Reduce volume 20% from today. 60 min Z2, HR cap LTHR-20, no elevation. "
            "Monitor resting HR — if +5 bpm above baseline, rest or swim."
        )
    elif context.acwr < 0.8:
        action = (
            "Aerobic endurance: 75-90 min Z2 with 6×20 sec strides at end. "
            "System below stimulus threshold — increase weekly volume 10%."
        )
    elif target and _is_ultra_target(target) and context.tsb > -15:
        phase = target.training_phase
        if phase == "Peak":
            action = (
                "Race simulation: 2-3h trail, 600m+ D+, last 30 min at marathon effort. "
                "Practice fueling every 30-40 min regardless of hunger."
            )
        elif phase == "Build":
            action = (
                "90 min trail with 400m D+. Include 3×10 min hill repeats at 8-12% grade. "
                "Downhill: cadence >180 spm, lean forward from ankles."
            )
        else:
            action = (
                "Easy trail 70 min Z2, HR cap LTHR-20. "
                "Strength: 3×15 single-leg squats + 3×20 calf raises."
            )
    else:
        action = (
            "Easy trail run 60 min, HR < LTHR-15 bpm. "
            "Hike uphills, run flats and downhills. Keep Z3 < 10%."
        )

    return f"{prefix}{action}"


def _nutrition_protocol(activity: ActivityInput) -> str:
    tss = activity.tss
    if tss < 60:
        carb, protein = 45, 15
        food = "Bánh mì (1 ổ thịt nguội) + nước dừa 300ml → ~45g carb + 15g protein + electrolytes"
        timing = "45 phút"
        ratio = "3:1"
    elif tss < 100:
        carb, protein = 60, 20
        food = "Cháo gà 1 tô lớn + bánh mì nhỏ → ~60g carb + 20g protein, electrolytes từ nước dùng"
        timing = "45 phút"
        ratio = "3:1"
    else:
        carb, protein = 80, 20
        food = "Phở bò (nhiều bánh, thêm thịt) + nước mía 300ml → ~85g carb + 22g protein + sodium từ nước dùng"
        timing = "30 phút"
        ratio = "4:1"

    kcal = int(tss * 6)
    return (
        f"TSS {tss:.0f} ≈ {kcal} kcal tiêu thụ. "
        f"Nạp trong {timing} (cửa sổ glycogen nhạy cảm insulin nhất). "
        f"Tỷ lệ {ratio}: {carb}g carb + {protein}g protein. "
        f"Gợi ý: {food}."
    )


def _vmm_projection(context: AthleteContext) -> str:
    if context.ctl <= 0 or context.threshold_pace_sec_km <= 0:
        return "Insufficient data for VMM projection. Log 8+ weeks of consistent training to enable."

    if context.ctl >= 90:
        multiplier, bracket = 2.4, "competitive (sub-28h)"
    elif context.ctl >= 70:
        multiplier, bracket = 2.6, "trained (28-32h)"
    elif context.ctl >= 50:
        multiplier, bracket = 2.9, "endurance (32-38h)"
    else:
        multiplier, bracket = 3.2, "completion (38-44h)"

    ultra_pace_sec_km = context.threshold_pace_sec_km * multiplier
    flat_time_sec = 160_000 / ultra_pace_sec_km
    elevation_penalty_sec = (10_000 / 10) * 60  # VMM ~10,000m D+, ~1 min per 10m
    total_sec = flat_time_sec + elevation_penalty_sec

    hours = int(total_sec // 3600)
    minutes = int((total_sec % 3600) // 60)

    if context.ctl < 70:
        limiter = "aerobic base (CTL below competitive threshold)"
        fix = f"Add 10% weekly volume for 8 weeks → target CTL {int(context.ctl + 15)}"
    elif context.acwr > 1.3:
        limiter = "recovery capacity (ACWR consistently above 1.3)"
        fix = "Insert 1 deload week per 3 weeks to build CTL sustainably"
    else:
        limiter = "sustained climbing power at 8-15% grades"
        fix = "2×/week hill repeats (10-15% grade, 8×2 min from week 1 to race week -3)"

    target = context.race_target
    label = f"{target.race_name} " if target else "VMM "
    weeks = f"{target.weeks_out}w to race. " if target else ""

    return (
        f"{label}160km projection: {hours}h{minutes:02d}m ({bracket}). "
        f"{weeks}#1 limiter: {limiter}. "
        f"Next bracket fix: {fix}."
    )


def _is_ultra_target(target: RaceTargetContext) -> bool:
    name = target.race_name.lower()
    return "vmm" in name or "utmb" in name or target.distance_km >= 80


def percent_of_average(value: float, average: float) -> float:
    if average <= 0:
        return 0.0
    return value / average * 100.0


# ---------------------------------------------------------------------------
# Plan-vs-actual fallback scoring
# ---------------------------------------------------------------------------

QUALITY_TYPES = frozenset({"tempo", "interval", "hill"})
EASY_TYPES = frozenset({"recovery", "easy"})


def compute_plan_compliance(
    *,
    planned: PlannedWorkoutContext,
    actual_tss: float,
    actual_duration_min: float,
    zone_distribution: dict[str, float],
) -> tuple[int, str]:
    """Return (score 0-100, headline sentence). Spec: see design doc §
    'Fallback scoring formula'."""
    score: float = 100.0

    # TSS axis — up to -40. Keep the `planned_tss > 0` guard to avoid
    # divide-by-zero, but do NOT guard on actual_tss: a planned session
    # with an actual TSS of 0 (skipped / barely-moved workout) must be
    # penalised, not score as "on target".
    if planned.planned_tss and planned.planned_tss > 0:
        delta = abs((actual_tss or 0.0) - planned.planned_tss) / planned.planned_tss
        score -= min(delta, 1.0) * 40

    # Duration axis — up to -30. Same reasoning as TSS axis above.
    if planned.planned_duration_min and planned.planned_duration_min > 0:
        delta = abs((actual_duration_min or 0.0) - planned.planned_duration_min) / planned.planned_duration_min
        score -= min(delta, 1.0) * 30

    # Type fidelity axis — flat -30
    type_break, type_reason = _detect_type_break(
        planned=planned,
        actual_duration_min=actual_duration_min,
        zone_distribution=zone_distribution,
    )
    if type_break:
        score -= 30

    score_int = max(0, round(score))

    # Headline priority: TYPE BREAK > overcooked > underdelivered > on target
    headline = _pick_headline(
        planned=planned,
        actual_tss=actual_tss,
        actual_duration_min=actual_duration_min,
        type_break=type_break,
        type_reason=type_reason,
    )
    return score_int, headline


def _detect_type_break(
    *,
    planned: PlannedWorkoutContext,
    actual_duration_min: float,
    zone_distribution: dict[str, float],
) -> tuple[bool, str]:
    z_hard = (
        zone_distribution.get("z3_pct", 0.0)
        + zone_distribution.get("z4_pct", 0.0)
        + zone_distribution.get("z5_pct", 0.0)
    )
    if planned.workout_type in EASY_TYPES and z_hard > 20:
        return True, "ran hard on an easy day"
    if planned.workout_type in QUALITY_TYPES and z_hard < 15:
        return True, "skipped the planned quality"
    if (
        planned.workout_type == "long"
        and planned.planned_duration_min
        and actual_duration_min < planned.planned_duration_min * 0.75
    ):
        return True, "cut the long run short"
    return False, ""


def _pick_headline(
    *,
    planned: PlannedWorkoutContext,
    actual_tss: float,
    actual_duration_min: float,
    type_break: bool,
    type_reason: str,
) -> str:
    overcooked_easy = (
        planned.planned_tss is not None
        and planned.planned_tss > 0
        and actual_tss > planned.planned_tss * 1.20
        and planned.workout_type in EASY_TYPES
    )
    # "Overcooked an easy day" subsumes the "ran hard on easy day" type break —
    # prefer the more informative headline when both apply.
    if overcooked_easy:
        return "Overcooked an easy day — tomorrow's quality session is now at risk."
    if type_break:
        return f"TYPE BREAK — {type_reason}."
    # Underdelivered: planned significant TSS but actual fell short. We
    # deliberately do NOT guard on `actual_duration_min > 10` here — a
    # skipped (0-min) day is exactly the case that most deserves this
    # headline, not "on target".
    if (
        planned.planned_tss
        and (actual_tss or 0.0) < planned.planned_tss * 0.80
    ):
        return "Plan underdelivered — diagnose why (HR drift, RPE, life stress, weather)."
    return "On target."


def format_plan_compliance_string(
    *,
    planned: PlannedWorkoutContext,
    actual_tss: float,
    actual_duration_min: float,
    zone_distribution: dict[str, float],
) -> str:
    score, headline = compute_plan_compliance(
        planned=planned,
        actual_tss=actual_tss,
        actual_duration_min=actual_duration_min,
        zone_distribution=zone_distribution,
    )
    return f"{score}/100 {headline}"
