# Strava's activity description field has a hard server-side cap. We stay
# comfortably under 4096 so a trailing ellipsis + the deep-dive URL always fit.
MAX_DESCRIPTION_CHARS = 4000
_TRUNCATION_SUFFIX = "…"


def acwr_zone_label(acwr: float) -> str:
    if acwr < 0.8:
        return "underload"
    if acwr <= 1.3:
        return "green"
    if acwr <= 1.5:
        return "caution"
    return "injury risk"


def format_strava_description(
    tss: float | None,
    acwr: float | None,
    z2_pct: float | None,
    hr_drift_pct: float | None,
    decoupling_pct: float | None,
    next_action: str,
    deep_dive_url: str,
    nutrition_protocol: str = "",
    vmm_projection: str = "",
) -> str:
    # Callers sometimes have partial metrics (e.g. a run with no HR stream
    # produces hr_drift=None). Coerce here so no new caller accidentally
    # triggers TypeError from the numeric format specs below.
    tss_v = float(tss or 0.0)
    acwr_v = float(acwr or 0.0)
    z2_v = float(z2_pct or 0.0)
    hr_drift_v = float(hr_drift_pct or 0.0)
    decoupling_v = float(decoupling_pct or 0.0)

    zone = acwr_zone_label(acwr_v)
    lines = [
        f"⚡ TSS {tss_v:.0f} · ACWR {acwr_v:.2f} ({zone}) · Z2 {z2_v:.0f}%",
        f"📉 HR drift {hr_drift_v:.1f}% · decoupling {decoupling_v:.1f}%",
    ]
    if nutrition_protocol:
        lines.append(f"🍜 {nutrition_protocol}")
    if vmm_projection:
        lines.append(f"🏔️ {vmm_projection}")
    lines += [
        f"→ {next_action}",
        f"🔍 {deep_dive_url}",
    ]
    description = "\n".join(lines)
    if len(description) <= MAX_DESCRIPTION_CHARS:
        return description
    # Preserve the trailing deep-dive URL — it's the link users click to see
    # the full report — and truncate the body above it.
    tail = f"\n🔍 {deep_dive_url}"
    budget = MAX_DESCRIPTION_CHARS - len(tail) - len(_TRUNCATION_SUFFIX)
    body_without_tail = description[: -len(tail)] if description.endswith(tail) else description
    return body_without_tail[:budget] + _TRUNCATION_SUFFIX + tail
