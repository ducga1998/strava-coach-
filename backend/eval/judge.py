"""LLM-as-judge dimensions. Independent Claude calls; never sees which model produced output."""
import logging
from typing import Any

import anthropic

from app.config import settings
from eval.fixtures import Fixture

logger = logging.getLogger(__name__)

_COHERENCE_TOOL: dict[str, Any] = {
    "name": "submit_coherence_score",
    "description": "Score coherence of the debrief against the input data",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 0, "maximum": 3, "description": "0=contradicts, 1=partial, 2=mostly, 3=fully consistent"},
            "reasoning": {"type": "string"},
        },
        "required": ["score", "reasoning"],
    },
}

_COHERENCE_SYSTEM = """\
You are an independent quality auditor. You will see (a) raw activity + athlete state metrics, and (b) a coaching debrief written by an unknown system.
Your only job: do all 5 fields of the debrief reference the SAME session and athlete state? Do they contradict each other or the input data?
Score 0-3:
0 = at least one field contradicts another or the input data
1 = fields are about different sessions (debrief is reused boilerplate)
2 = mostly consistent but at least one field is unrelated to today's session
3 = all 5 fields consistently reference today's session and athlete state
You do not know who wrote the debrief. Do not speculate about the model. Score on coherence only.
"""


async def judge_coherence(
    debrief: dict[str, str],
    fixture: Fixture,
    client: anthropic.AsyncAnthropic | Any | None = None,
) -> int:
    real_client = client or anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_prompt = (
        f"=== INPUT METRICS ===\n"
        f"Activity: {fixture.activity.activity_name} | TSS {fixture.activity.tss} | "
        f"HR drift {fixture.activity.hr_drift_pct}% | decoupling {fixture.activity.aerobic_decoupling_pct}%\n"
        f"Athlete: ACWR {fixture.context.acwr} | CTL {fixture.context.ctl} | TSB {fixture.context.tsb}\n\n"
        f"=== DEBRIEF ===\n"
        f"load_verdict: {debrief.get('load_verdict', '')}\n"
        f"technical_insight: {debrief.get('technical_insight', '')}\n"
        f"next_session_action: {debrief.get('next_session_action', '')}\n"
        f"nutrition_protocol: {debrief.get('nutrition_protocol', '')}\n"
        f"vmm_projection: {debrief.get('vmm_projection', '')}\n\n"
        f"Score the coherence (0-3) and explain in one sentence."
    )
    response = await real_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=_COHERENCE_SYSTEM,
        tools=[_COHERENCE_TOOL],
        tool_choice={"type": "tool", "name": "submit_coherence_score"},
        messages=[{"role": "user", "content": user_prompt}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_coherence_score":
            score = block.input.get("score", 0)
            return score if 0 <= score <= 3 else 0
    return 0
