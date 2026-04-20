_DIVIDER = "─" * 17


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
    feedback_url: str,
    nutrition_protocol: str = "",
    vmm_projection: str = "",
) -> str:
    """Build a Strava activity description split into visually distinct blocks.

    Layout:
        metrics (2 lines)
        [blank]
        coaching  (0-2 lines, omitted entirely when both inputs empty)
        [blank]
        → Next:  (omitted when next_action empty)
        [blank]
        ──────
        📊 Deep dive:  <url>
        💬 Feedback:   <url>
    """
    zone = acwr_zone_label(acwr)
    blocks: list[list[str]] = []

    blocks.append([
        f"⚡ TSS {tss:.0f}  ·  ACWR {acwr:.2f} {zone}",
        f"   Z2 {z2_pct:.0f}%  ·  HR drift {hr_drift_pct:.1f}%  ·  Decoupling {decoupling_pct:.1f}%",
    ])

    coaching: list[str] = []
    if nutrition_protocol:
        coaching.append(f"🍜 Fuel: {nutrition_protocol}")
    if vmm_projection:
        coaching.append(f"🏔️ VMM: {vmm_projection}")
    if coaching:
        blocks.append(coaching)

    if next_action:
        blocks.append([f"→ Next: {next_action}"])

    blocks.append([
        _DIVIDER,
        f"📊 Deep dive:  {deep_dive_url}",
        f"💬 Feedback:   {feedback_url}",
    ])

    return "\n\n".join("\n".join(block) for block in blocks)
