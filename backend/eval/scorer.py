"""Deterministic scorers for debrief output. Each returns 0-3."""
import re

_FIELDS = ("load_verdict", "technical_insight", "next_session_action", "nutrition_protocol", "vmm_projection")
_HAS_DIGIT = re.compile(r"\d")


def score_specificity(debrief: dict[str, str]) -> int:
    fields_with_numbers = sum(1 for f in _FIELDS if _HAS_DIGIT.search(debrief.get(f, "")))
    if fields_with_numbers == 5:
        return 3
    if fields_with_numbers == 4:
        return 2
    if fields_with_numbers == 3:
        return 1
    return 0


_GENERIC_PHRASES = ("great job", "keep it up", "listen to your body")


def score_no_generics(debrief: dict[str, str]) -> int:
    combined = " ".join(debrief.get(f, "") for f in _FIELDS).lower()
    return 0 if any(phrase in combined for phrase in _GENERIC_PHRASES) else 3


_BAND_ALIASES: dict[str, tuple[str, ...]] = {
    "underload": ("underload",),
    "green": ("green", "optimal", "sweet spot"),
    "caution": ("caution", "overreach"),
    "injury risk": ("injury risk", "danger", "danger zone"),
}


def score_acwr_band(debrief: dict[str, str], expected_band: str) -> int:
    text = debrief.get("load_verdict", "").lower()
    aliases = _BAND_ALIASES.get(expected_band, (expected_band,))
    return 3 if any(alias in text for alias in aliases) else 0


def score_nutrition_ratio(debrief: dict[str, str], tss: float) -> int:
    expected = "4:1" if tss >= 100 else "3:1"
    text = debrief.get("nutrition_protocol", "")
    return 3 if expected in text else 0


_TIME_PATTERN = re.compile(r"(\d+)\s*h\s*(\d+)?\s*m?", re.IGNORECASE)


def _expected_vmm_hours(ctl: float, threshold_pace_sec_km: float) -> float:
    if ctl >= 90:
        multiplier = 2.4
    elif ctl >= 70:
        multiplier = 2.6
    elif ctl >= 50:
        multiplier = 2.9
    else:
        multiplier = 3.2
    flat_sec = 160_000 / (threshold_pace_sec_km * multiplier) * 60
    elevation_sec = (10_000 / 10) * 60
    return (flat_sec + elevation_sec) / 3600


def score_vmm_math(debrief: dict[str, str], ctl: float, threshold_pace_sec_km: float) -> int:
    text = debrief.get("vmm_projection", "")
    match = _TIME_PATTERN.search(text)
    if not match:
        return 0
    hours = int(match.group(1))
    minutes = int(match.group(2)) if match.group(2) else 0
    actual = hours + minutes / 60
    expected = _expected_vmm_hours(ctl, threshold_pace_sec_km)
    delta = abs(actual - expected)
    if delta <= 3:
        return 3
    if delta <= 6:
        return 2
    if delta <= 10:
        return 1
    return 0
