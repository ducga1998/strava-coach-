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
