from app.agents.schema import ActivityInput, AthleteContext, DebriefOutput

GENERIC_PHRASES = ("great job", "keep it up", "listen to your body")


async def generate_debrief(
    activity: ActivityInput, context: AthleteContext
) -> dict[str, str]:
    return fallback_debrief(activity, context).model_dump()


def fallback_debrief(
    activity: ActivityInput, context: AthleteContext
) -> DebriefOutput:
    tss_pct = percent_of_average(activity.tss, context.tss_30d_avg)
    zone = acwr_zone(context.acwr)
    return DebriefOutput(
        load_verdict=(
            f"TSS {activity.tss:.0f} is {tss_pct:.0f}% of 30-day average; "
            f"ACWR {context.acwr:.2f} is {zone}."
        ),
        technical_insight=(
            f"HR drift {activity.hr_drift_pct:.1f}% and decoupling "
            f"{activity.aerobic_decoupling_pct:.1f}% with "
            f"Z2 {activity.zone_distribution.get('z2_pct', 0.0):.0f}%."
        ),
        next_session_action=next_session_action(context.acwr, context.tsb),
    )


def percent_of_average(value: float, average: float) -> float:
    if average <= 0:
        return 0.0
    return value / average * 100.0


def acwr_zone(acwr: float) -> str:
    if acwr < 0.8:
        return "underload"
    if acwr <= 1.3:
        return "green"
    if acwr <= 1.5:
        return "caution"
    return "injury risk"


def next_session_action(acwr: float, tsb: float) -> str:
    if acwr > 1.5 or tsb < -30:
        return "Recovery run 40-50 min in Z1-Z2, HR below LTHR minus 30 bpm."
    if acwr < 0.8:
        return "Aerobic endurance run 75-90 min in Z2 with 6 x 20 sec strides."
    return "Easy trail run 60 min in Z2, keep climbs below threshold effort."
