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
