"""Default variant: re-exports the live production prompt."""
from app.agents.prompts import SYSTEM_PROMPT, build_debrief_prompt

__all__ = ["SYSTEM_PROMPT", "build_debrief_prompt"]
