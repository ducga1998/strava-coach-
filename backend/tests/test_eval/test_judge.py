import asyncio
from unittest.mock import AsyncMock, MagicMock

from eval.fixtures import F1
from eval.judge import judge_coherence


def test_judge_coherence_extracts_score_from_tool_use() -> None:
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "submit_coherence_score"
    mock_block.input = {"score": 3, "reasoning": "Fields agree."}

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    debrief = {
        "load_verdict": "TSS 45.",
        "technical_insight": "All metrics nominal.",
        "next_session_action": "60 min Z2.",
        "nutrition_protocol": "3:1 ratio.",
        "vmm_projection": "20h30m.",
    }
    score = asyncio.run(judge_coherence(debrief, F1, client=mock_client))
    assert score == 3
    mock_client.messages.create.assert_awaited_once()


def test_judge_coherence_clamps_invalid_score_to_zero() -> None:
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "submit_coherence_score"
    mock_block.input = {"score": 99, "reasoning": "Invalid."}

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    debrief = {"load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "", "vmm_projection": ""}
    score = asyncio.run(judge_coherence(debrief, F1, client=mock_client))
    assert score == 0


from eval.judge import judge_coach_value


def test_judge_coach_value_extracts_float_score() -> None:
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "submit_coach_value_score"
    mock_block.input = {"score": 4.2, "reasoning": "Specific numbers, actionable."}

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    debrief = {"load_verdict": "TSS 45.", "technical_insight": "All nominal.", "next_session_action": "60 min Z2.", "nutrition_protocol": "3:1.", "vmm_projection": "20h30m."}
    score = asyncio.run(judge_coach_value(debrief, F1, client=mock_client))
    assert 4.0 <= score <= 4.5


def test_judge_coach_value_clamps_out_of_range() -> None:
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "submit_coach_value_score"
    mock_block.input = {"score": 99.0, "reasoning": ""}

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    debrief = {"load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "", "vmm_projection": ""}
    score = asyncio.run(judge_coach_value(debrief, F1, client=mock_client))
    assert score == 1.0


from unittest.mock import patch

from eval.runner import run_fixture
from eval.matrix import FixtureResult


def test_run_fixture_returns_both_modes() -> None:
    fake_llm_debrief = {
        "load_verdict": "TSS 45 over 55 average. ACWR 1.0 → green.",
        "technical_insight": "All metrics nominal.",
        "next_session_action": "60 min Z2 run, HR cap LTHR-15 bpm.",
        "nutrition_protocol": "3:1 ratio: 45g carb + 15g protein in 45 phút.",
        "vmm_projection": "VMM 160km projection: 22h30m.",
    }

    async def fake_llm(*args, **kwargs):
        return fake_llm_debrief

    async def fake_judge_coh(*args, **kwargs):
        return 3

    async def fake_judge_cv(*args, **kwargs):
        return 4.0

    with (
        patch("eval.runner._call_llm_debrief", side_effect=fake_llm),
        patch("eval.runner.judge_coherence", side_effect=fake_judge_coh),
        patch("eval.runner.judge_coach_value", side_effect=fake_judge_cv),
    ):
        result = asyncio.run(run_fixture(F1, prompt_variant="current"))

    assert isinstance(result, FixtureResult)
    assert result.fixture_id == "F1"
    assert result.llm.coherence == 3
    assert result.llm.coach_value == 4.0
    assert result.fallback.deterministic.specificity > 0
