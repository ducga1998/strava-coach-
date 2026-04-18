def acwr_zone_label(acwr: float) -> str:
    if acwr < 0.8:
        return "underload"
    if acwr <= 1.3:
        return "green"
    if acwr <= 1.5:
        return "caution"
    return "injury risk"


def format_strava_description(
    tss: float,
    acwr: float,
    z2_pct: float,
    hr_drift_pct: float,
    decoupling_pct: float,
    next_action: str,
    deep_dive_url: str,
) -> str:
    zone = acwr_zone_label(acwr)
    return (
        f"⚡ TSS {tss:.0f} · ACWR {acwr:.2f} ({zone}) · Z2 {z2_pct:.0f}%\n"
        f"📉 HR drift {hr_drift_pct:.1f}% · decoupling {decoupling_pct:.1f}%\n"
        f"→ {next_action}\n"
        f"🔍 {deep_dive_url}"
    )
