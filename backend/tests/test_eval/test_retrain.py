import textwrap
from pathlib import Path

import pytest

from eval.retrain import discover_variants, promote_variant, render_leaderboard
from eval.ranking import VariantRank


def test_discover_variants_sorted_excludes_init(tmp_path: Path) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "__init__.py").write_text("")
    (prompts / "zebra.py").write_text("SYSTEM_PROMPT = 'z'\nbuild_debrief_prompt = lambda a, b: 'z'\n")
    (prompts / "alpha.py").write_text("SYSTEM_PROMPT = 'a'\nbuild_debrief_prompt = lambda a, b: 'a'\n")
    variants = discover_variants(prompts_dir=prompts)
    assert variants == ["alpha", "zebra"]


def test_discover_variants_empty_returns_empty(tmp_path: Path) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "__init__.py").write_text("")
    assert discover_variants(prompts_dir=prompts) == []


def test_render_leaderboard_marks_winner() -> None:
    ranks = [
        VariantRank("tighter", 85.0, 60.0, 16.0, 3.0, 4.5),
        VariantRank("current", 75.0, 60.0, 14.0, 3.0, 4.2),
    ]
    out = render_leaderboard(ranks)
    assert "🏆" in out
    assert "tighter" in out
    assert "85.0" in out


def test_promote_variant_replaces_system_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompts_file = tmp_path / "prompts.py"
    prompts_file.write_text(textwrap.dedent('''\
        SYSTEM_PROMPT = """\\
        OLD PROMPT CONTENT
        More old lines.
        """


        def build_debrief_prompt(a, b):
            return "built"
        '''))

    # Create a fake variant module we can import
    import sys
    import types

    fake_module = types.ModuleType("eval.prompts.test_winner")
    fake_module.SYSTEM_PROMPT = "NEW PROMPT CONTENT\nwith multiple lines."
    fake_module.build_debrief_prompt = lambda a, b: "built"
    monkeypatch.setitem(sys.modules, "eval.prompts.test_winner", fake_module)

    promote_variant("test_winner", prompts_file=prompts_file)

    updated = prompts_file.read_text()
    assert "NEW PROMPT CONTENT" in updated
    assert "OLD PROMPT CONTENT" not in updated
    # build_debrief_prompt must remain intact
    assert "def build_debrief_prompt(a, b):" in updated


def test_promote_variant_raises_when_no_system_prompt_block(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    prompts_file = tmp_path / "prompts.py"
    prompts_file.write_text("# no SYSTEM_PROMPT here\n")

    fake_module = types.ModuleType("eval.prompts.noop")
    fake_module.SYSTEM_PROMPT = "doesn't matter"
    monkeypatch.setitem(sys.modules, "eval.prompts.noop", fake_module)

    with pytest.raises(RuntimeError, match="Could not find SYSTEM_PROMPT"):
        promote_variant("noop", prompts_file=prompts_file)


def test_promote_variant_raises_on_empty_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    prompts_file = tmp_path / "prompts.py"
    prompts_file.write_text('SYSTEM_PROMPT = """hi"""\n')

    fake_module = types.ModuleType("eval.prompts.empty")
    fake_module.SYSTEM_PROMPT = "   "
    monkeypatch.setitem(sys.modules, "eval.prompts.empty", fake_module)

    with pytest.raises(RuntimeError, match="empty SYSTEM_PROMPT"):
        promote_variant("empty", prompts_file=prompts_file)
