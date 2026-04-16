SYSTEM_PROMPT = """You are an elite ultra and trail running coach.
Every claim must be backed by a number from the input metrics.
Never use generic phrases like great job, keep it up, or listen to your body.
Respond only with valid JSON matching load_verdict, technical_insight, and next_session_action.
"""


def build_debrief_prompt(activity: dict[str, object], context: dict[str, object]) -> str:
    return "\n".join(
        [
            f"Training phase: {context['training_phase']}",
            f"CTL: {context['ctl']} ATL: {context['atl']} TSB: {context['tsb']}",
            f"ACWR: {context['acwr']} 30-day TSS avg: {context['tss_30d_avg']}",
            f"Activity: {activity['activity_name']} {activity['sport_type']}",
            f"Duration: {activity['duration_sec']} Distance: {activity['distance_m']}",
            f"TSS: {activity['tss']} hrTSS: {activity['hr_tss']}",
            f"HR drift: {activity['hr_drift_pct']} Decoupling: {activity['aerobic_decoupling_pct']}",
            f"NGP: {activity['ngp_sec_km']} Zones: {activity['zone_distribution']}",
        ]
    )
