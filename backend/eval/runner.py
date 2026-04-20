"""Orchestrates one fixture × both modes (LLM + fallback) and scores both."""
import importlib
import logging
from typing import Any

import anthropic

from app.agents.debrief_graph import _DEBRIEF_TOOL, fallback_debrief
from app.config import settings
from eval.fixtures import Fixture
from eval.judge import judge_coach_value, judge_coherence
from eval.matrix import FixtureResult, ModeResult
from eval.scorer import score_deterministic

logger = logging.getLogger(__name__)


def _load_prompt_variant(variant: str) -> tuple[str, Any]:
    """Returns (SYSTEM_PROMPT, build_debrief_prompt) from named variant module."""
    if variant == "current":
        from app.agents.prompts import SYSTEM_PROMPT, build_debrief_prompt
        return SYSTEM_PROMPT, build_debrief_prompt
    module = importlib.import_module(f"eval.prompts.{variant}")
    return module.SYSTEM_PROMPT, module.build_debrief_prompt


async def _call_llm_debrief(
    fixture: Fixture, system_prompt: str, build_prompt: Any
) -> dict[str, str]:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_prompt = build_prompt(fixture.activity.model_dump(), fixture.context.model_dump())
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=system_prompt,
        tools=[_DEBRIEF_TOOL],
        tool_choice={"type": "tool", "name": "submit_debrief"},
        messages=[{"role": "user", "content": user_prompt}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_debrief":
            return block.input
    raise RuntimeError("LLM did not return submit_debrief tool use")


async def _score_mode(
    debrief: dict[str, str], fixture: Fixture, mode_label: str
) -> ModeResult:
    deterministic = score_deterministic(debrief, fixture)
    coherence = await judge_coherence(debrief, fixture)
    coach_value = await judge_coach_value(debrief, fixture)
    return ModeResult(
        mode=mode_label,
        deterministic=deterministic,
        coherence=coherence,
        coach_value=coach_value,
        debrief=debrief,
    )


async def run_fixture(fixture: Fixture, prompt_variant: str) -> FixtureResult:
    system_prompt, build_prompt = _load_prompt_variant(prompt_variant)

    try:
        llm_debrief = await _call_llm_debrief(fixture, system_prompt, build_prompt)
    except Exception:
        logger.exception("LLM debrief failed for fixture %s; using empty placeholder", fixture.id)
        llm_debrief = {k: "" for k in ("load_verdict", "technical_insight", "next_session_action", "nutrition_protocol", "vmm_projection")}

    fb_debrief = fallback_debrief(fixture.activity, fixture.context).model_dump()

    llm_result = await _score_mode(llm_debrief, fixture, "LLM")
    fb_result = await _score_mode(fb_debrief, fixture, "Fallback")

    return FixtureResult(
        fixture_id=fixture.id,
        fixture_name=fixture.name,
        llm=llm_result,
        fallback=fb_result,
    )
