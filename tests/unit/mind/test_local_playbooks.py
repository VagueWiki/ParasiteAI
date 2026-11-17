"""Unit tests validating shipped local SKILL.md playbooks in data/skills/."""

from __future__ import annotations

from pathlib import Path

import pytest

from parasite_ai.config import SkillsConfig
from parasite_ai.mind.parasite_protocol import find_coordinate_patterns
from parasite_ai.mind.skills import SkillRegistry

pytestmark = pytest.mark.unit


def test_shipped_local_playbooks_load_match_and_compile_with_directives() -> None:
    skills_dir = Path("data/skills")
    reg = SkillRegistry(SkillsConfig(enabled=True, skills_dir=skills_dir))
    report = reg.load_all()

    assert report.errors == []
    for expected_id in (
        "open-notepad-notes",
        "notepad-write-text",
        "calculator-evaluate",
        "paint-new-and-save",
    ):
        assert expected_id in reg.skills

    cases = [
        ("open notepad and type hello world", "notepad-write-text", ["win", "r"], "notepad", "hello world"),
        ("Open Notepad and write 'Benchmark Alpha Test 42'", "notepad-write-text", ["win", "r"], "notepad", "Benchmark Alpha Test 42"),
        ("calculate 12*7", "calculator-evaluate", ["win", "r"], "calc", "12*7"),
        ("Open Calculator and compute 7 * 8", "calculator-evaluate", ["win", "r"], "calc", "7 * 8"),
        ("open paint and save as 'test_canvas.png'", "paint-new-and-save", ["win", "r"], "mspaint", "test_canvas.png"),
    ]
    for goal, skill_id, launch_keys, launch_text, param_text in cases:
        match = reg.match(goal, active_process="explorer.exe")
        assert match is not None, f"Failed to match goal: {goal}"
        assert match.skill.id == skill_id

        lp = reg.compile_to_living_plan(match, goal, active_process="explorer.exe")
        # Launch triple prepended (HOTKEY win/win+r + TYPE launch_text)
        assert lp.steps[0].rationale == "launch:open_start"
        assert lp.steps[0].directive is not None
        assert lp.steps[0].directive.verb == "HOTKEY"
        assert lp.steps[0].directive.keys == launch_keys

        assert lp.steps[1].rationale == "launch:submit_search"
        assert lp.steps[1].directive is not None
        assert lp.steps[1].directive.verb == "TYPE"
        assert lp.steps[1].directive.text == launch_text
        assert lp.steps[1].directive.submit is True

        # Substituted parameter appears in a directive step, with zero coordinates anywhere
        directive_texts = [
            s.directive.text for s in lp.steps[2:] if s.directive is not None and s.directive.text
        ]
        assert param_text in directive_texts
        for s in lp.steps:
            assert find_coordinate_patterns(s.description) == []
            if s.directive and s.directive.text:
                assert find_coordinate_patterns(s.directive.text) == []

    # Promoted candidate skills load non-draft, score >= min_score, and preserve submit=True
    for promoted_id in ("minimize-notepad", "open-notepad-type-draft-select-all-text-and-copy"):
        assert promoted_id in reg.skills
        assert reg.skills[promoted_id].draft is False

    min_match = reg.match("Minimize Notepad", active_process="explorer.exe")
    assert min_match is not None and min_match.skill.id == "minimize-notepad"

    draft_match = reg.match("Open Notepad, type 'Draft', select all text, and copy", active_process="explorer.exe")
    assert draft_match is not None
    assert draft_match.skill.id == "open-notepad-type-draft-select-all-text-and-copy"
    draft_plan = reg.compile_to_living_plan(draft_match, "Open Notepad, type 'Draft', select all text, and copy")
    assert draft_plan.steps[0].directive is not None and draft_plan.steps[0].directive.keys == ["win", "r"]
    assert draft_plan.steps[1].directive is not None and draft_plan.steps[1].directive.text == "notepad"
    assert draft_plan.steps[1].directive.submit is True


def test_try_directive_fast_path_uwp_and_run_dialog_launch_input() -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from parasite_ai.mind.dual_mind import DualMindPipeline
    from parasite_ai.mind.plan import PlanStep, StepDirective, StepIntent

    pipeline = DualMindPipeline(brain_manager=MagicMock())
    pipeline.window_guard = None

    # 1. UWP ApplicationFrameHost.exe ("Calculator") matches expected CalculatorApp.exe
    step_calc = PlanStep(
        step_id=3,
        intent=StepIntent.INPUT_DATA,
        description="Type expression",
        success_criteria="Typed",
        directive=StepDirective(verb="HOTKEY", keys=["escape"]),
    )
    uwp_win = SimpleNamespace(process_name="ApplicationFrameHost.exe", title="Calculator")
    res_calc = pipeline._try_directive_fast_path(step_calc, uwp_win, "CalculatorApp.exe", None)
    assert res_calc is not None
    assert res_calc[1].keys == ["escape"]

    # 2. Early step_id=2 TYPE submit=True inside Run (explorer.exe) executes on fast path
    step_run = PlanStep(
        step_id=2,
        intent=StepIntent.INPUT_DATA,
        description="Type notepad in Run",
        success_criteria="Opened",
        directive=StepDirective(verb="TYPE", text="notepad", submit=True),
    )
    run_win = SimpleNamespace(process_name="explorer.exe", title="Run")
    res_run = pipeline._try_directive_fast_path(step_run, run_win, "notepad.exe", None)
    assert res_run is not None
    assert res_run[1].text == "notepad"
    assert res_run[1].submit is True

