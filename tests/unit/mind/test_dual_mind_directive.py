"""Unit tests for P4.5.2 gated directive fast path and directive-aware step verification."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from parasite_ai.config import AppConfig
from parasite_ai.mind.dual_mind import ActionResult, DualMindPipeline
from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.mind.plan import (
    LivingPlan,
    PlanStep,
    StepDirective,
    StepIntent,
    StepStatus,
    verify_step_completion,
)
from parasite_ai.safety.risk_gate import ActionRisk

pytestmark = pytest.mark.unit


def _make_pipeline(safe_window: bool = True, process_name: str = "notepad.exe"):
    cfg = AppConfig()

    brain = MagicMock()
    brain.generate_cua_step.return_value = (
        "VLM fallback",
        ActionPlan(action=ActionType.WAIT, wait_ms=100, reasoning="vlm"),
    )

    capturer = MagicMock()
    capturer.capture_screen.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

    window_guard = MagicMock()
    window_guard.is_safe_to_operate.return_value = safe_window
    window_guard.get_active_window.return_value = SimpleNamespace(
        title="Untitled - Notepad",
        process_name=process_name,
        rect=(0, 0, 800, 600),
    )

    mouse = MagicMock()
    kb = MagicMock()
    kb.type_text.return_value = True
    kb.hotkey.return_value = True

    pipe = DualMindPipeline(
        brain_manager=brain,
        mouse_driver=mouse,
        keyboard_driver=kb,
        capturer=capturer,
        window_guard=window_guard,
        config=cfg,
    )
    pipe._is_cua_mode_active = MagicMock(return_value=True)
    return pipe, brain, kb, window_guard


def test_directive_fast_path_executes_type_hotkey_wait_without_vlm() -> None:
    pipe, brain, kb, _ = _make_pipeline()
    pipe.active_plan = LivingPlan(
        user_goal="type hello",
        overall_strategy="Skill Playbook: test",
        steps=[
            PlanStep(
                step_id=1,
                intent=StepIntent.INPUT_DATA,
                description="Type hello",
                success_criteria="Text appears",
                status=StepStatus.IN_PROGRESS,
                directive=StepDirective(verb="TYPE", text="hello", submit=True),
            ),
            PlanStep(
                step_id=2,
                intent=StepIntent.NAVIGATE,
                description="Save",
                success_criteria="Saved",
                status=StepStatus.PENDING,
                directive=StepDirective(verb="HOTKEY", keys=["ctrl", "s"]),
            ),
            PlanStep(
                step_id=3,
                intent=StepIntent.VERIFY_STATE,
                description="Wait",
                success_criteria="Settled",
                status=StepStatus.PENDING,
                directive=StepDirective(verb="WAIT", wait_ms=250),
            ),
        ],
        current_step_id=1,
    )

    with patch("parasite_ai.mind.dual_mind.check_caret_focus", return_value=True):
        rec1 = pipe.step("type hello")
    assert rec1.action.action == ActionType.TYPE
    assert rec1.action.text == "hello"
    assert rec1.action.submit is True
    assert rec1.action.clear_first is False
    assert brain.generate_cua_step.call_count == 0
    assert pipe._episode_fast_path_steps == 1

    # Advance to step 2 (HOTKEY)
    pipe.active_plan.current_step_id = 2
    pipe.active_plan.steps[1].status = StepStatus.IN_PROGRESS
    rec2 = pipe.step("type hello")
    assert rec2.action.action == ActionType.HOTKEY
    assert rec2.action.keys == ["ctrl", "s"]
    assert brain.generate_cua_step.call_count == 0
    assert pipe._episode_fast_path_steps == 2

    # Advance to step 3 (WAIT)
    pipe.active_plan.current_step_id = 3
    pipe.active_plan.steps[2].status = StepStatus.IN_PROGRESS
    rec3 = pipe.step("type hello")
    assert rec3.action.action == ActionType.WAIT
    assert rec3.action.wait_ms == 250
    assert brain.generate_cua_step.call_count == 0
    assert pipe._episode_fast_path_steps == 3


def test_directive_fast_path_pointer_verb_always_uses_vlm_with_hint() -> None:
    pipe, brain, _, _ = _make_pipeline()
    pipe.active_plan = LivingPlan(
        user_goal="click save",
        overall_strategy="Skill Playbook: test",
        steps=[
            PlanStep(
                step_id=1,
                intent=StepIntent.NAVIGATE,
                description="Click Save",
                target_description="Save button",
                success_criteria="Saved",
                status=StepStatus.IN_PROGRESS,
                directive=StepDirective(verb="CLICK"),
            ),
        ],
        current_step_id=1,
    )
    pipe.step("click save")
    assert brain.generate_cua_step.call_count == 1
    wm = brain.generate_cua_step.call_args.kwargs.get("working_memory_context", "")
    assert "Required action: CLICK" in wm


def test_directive_fast_path_gates_fail_closed_to_vlm() -> None:
    # 1. No caret -> falls back to VLM
    pipe, brain, _, _ = _make_pipeline()
    step = PlanStep(
        step_id=1,
        intent=StepIntent.INPUT_DATA,
        description="Type",
        success_criteria="Typed",
        status=StepStatus.IN_PROGRESS,
        directive=StepDirective(verb="TYPE", text="abc"),
    )
    with patch("parasite_ai.mind.dual_mind.check_caret_focus", return_value=False):
        assert pipe._try_directive_fast_path(step, None, None, None) is None

    # 2. Launch submit_search bypasses caret check
    launch_step = step.model_copy(update={"rationale": "launch:submit_search"})
    with patch("parasite_ai.mind.dual_mind.check_caret_focus", return_value=False):
        res = pipe._try_directive_fast_path(launch_step, None, None, None)
        assert res is not None and res[1].action == ActionType.TYPE

    # 3. One-shot guard prevents repeating fast-path on same step_id
    assert pipe._try_directive_fast_path(launch_step, None, None, None) is None

    # 4. Unsafe window blocks fast-path
    pipe2, _, _, _ = _make_pipeline(safe_window=False)
    hk_step = PlanStep(
        step_id=5,
        intent=StepIntent.NAVIGATE,
        description="Save",
        success_criteria="Saved",
        directive=StepDirective(verb="HOTKEY", keys=["ctrl", "s"]),
    )
    assert pipe2._try_directive_fast_path(hk_step, None, None, None) is None

    # 5. Process mismatch on in-app step blocks fast-path
    pipe3, _, _, wg3 = _make_pipeline(safe_window=True, process_name="explorer.exe")
    assert pipe3._try_directive_fast_path(hk_step, wg3.get_active_window(), "notepad.exe", None) is None

    # 6. Cancelled token blocks fast-path
    tok = threading.Event()
    tok.set()
    assert pipe3._try_directive_fast_path(hk_step, wg3.get_active_window(), "explorer.exe", tok) is None
    assert brain.generate_cua_step.call_count == 0


def test_directive_fast_path_respects_yellow_risk_consent_gate() -> None:
    pipe, brain, _, _ = _make_pipeline()
    consent_calls = []
    pipe.consent_handler = lambda req: (consent_calls.append(req), False)[1]
    pipe.active_plan = LivingPlan(
        user_goal="close app",
        overall_strategy="Skill Playbook: test",
        steps=[
            PlanStep(
                step_id=1,
                intent=StepIntent.NAVIGATE,
                description="Close window",
                success_criteria="Closed",
                status=StepStatus.IN_PROGRESS,
                directive=StepDirective(verb="HOTKEY", keys=["alt", "f4"]),
            )
        ],
        current_step_id=1,
    )
    rec = pipe.step("close app")
    assert brain.generate_cua_step.call_count == 0
    assert len(consent_calls) == 1
    assert consent_calls[0].risk in (ActionRisk.YELLOW, ActionRisk.RED)
    assert rec.success is False


def test_verify_step_completion_directive_aware() -> None:
    wait_step = PlanStep(
        step_id=1,
        intent=StepIntent.VERIFY_STATE,
        description="Wait",
        success_criteria="Done",
        directive=StepDirective(verb="WAIT", wait_ms=200),
    )
    ok_res = ActionResult(success=True)
    assert verify_step_completion(wait_step, ActionPlan(action=ActionType.WAIT), ok_res, screen_diff=0.0) is True

    hk_step = PlanStep(
        step_id=2,
        intent=StepIntent.NAVIGATE,
        description="Save",
        success_criteria="Dialog",
        directive=StepDirective(verb="HOTKEY", keys=["ctrl", "s"]),
    )
    assert verify_step_completion(hk_step, ActionPlan(action=ActionType.HOTKEY), ok_res, screen_diff=0.005) is False
    assert verify_step_completion(hk_step, ActionPlan(action=ActionType.HOTKEY), ok_res, screen_diff=0.03) is True

    type_step = PlanStep(
        step_id=3,
        intent=StepIntent.INPUT_DATA,
        description="Type",
        success_criteria="Typed",
        directive=StepDirective(verb="TYPE", text="abc"),
    )
    assert verify_step_completion(type_step, ActionPlan(action=ActionType.TYPE), ok_res, screen_diff=0.001) is False
    assert verify_step_completion(type_step, ActionPlan(action=ActionType.TYPE), ok_res, screen_diff=0.01) is True


def test_completed_plan_is_not_reinitialized_within_same_episode():
    """P4.5.9: Completed LivingPlan for the same user_goal must not loop back to step 1."""
    pipeline, *_ = _make_pipeline()
    completed_plan = LivingPlan(
        user_goal="calculate 12*7",
        steps=[
            PlanStep(
                step_id=1,
                intent=StepIntent.NAVIGATE,
                description="Press Enter",
                success_criteria="Done",
                status=StepStatus.COMPLETED,
                directive=StepDirective(verb="HOTKEY", keys=["enter"]),
            )
        ],
        current_step_index=1,
    )
    assert completed_plan.is_completed() is True
    pipeline.active_plan = completed_plan
    pipeline.skill_registry = MagicMock()

    returned = pipeline._initialize_or_update_plan("calculate 12*7")
    assert returned is completed_plan
    assert returned.is_completed() is True
    pipeline.skill_registry.match.assert_not_called()


def test_verify_step_completion_rejects_mismatched_action_verb_for_directive():
    """P4.5.9: Recovery CLICK must not advance past an unexecuted TYPE directive step."""
    ok_res = ActionResult(success=True)
    type_step = PlanStep(
        step_id=4,
        intent=StepIntent.INPUT_DATA,
        description="Type target filename",
        success_criteria="Typed",
        directive=StepDirective(verb="TYPE", text="out.png"),
    )
    assert verify_step_completion(type_step, ActionPlan(action=ActionType.CLICK, x=10, y=10), ok_res, screen_diff=0.25) is False
    assert verify_step_completion(type_step, ActionPlan(action=ActionType.TYPE, text="out.png"), ok_res, screen_diff=0.01) is True


def test_verify_step_completion_allows_launch_hotkey_into_run_dialog():
    """P4.5.9: LAUNCH_OR_ACTIVATE HOTKEY (win+r) completes when Run (explorer.exe) opens."""
    ok_res = ActionResult(success=True)
    launch_hotkey_step = PlanStep(
        step_id=1,
        intent=StepIntent.LAUNCH_OR_ACTIVATE,
        description="Open Run dialog",
        target_description="Windows keyboard shortcut",
        success_criteria="Run dialog open",
        directive=StepDirective(verb="HOTKEY", keys=["win", "r"]),
    )
    run_win = SimpleNamespace(title="Run", process_name="explorer.exe")
    assert (
        verify_step_completion(
            launch_hotkey_step,
            ActionPlan(action=ActionType.HOTKEY, keys=["win", "r"]),
            ok_res,
            screen_diff=0.10,
            current_window=run_win,
        )
        is True
    )
    assert (
        verify_step_completion(
            launch_hotkey_step,
            ActionPlan(action=ActionType.HOTKEY, keys=["win", "r"]),
            ok_res,
            screen_diff=0.005,
            current_window=run_win,
        )
        is False
    )


def test_directive_fast_path_post_launch_readiness_wait_and_fallback() -> None:
    pipe, brain, _, wg = _make_pipeline(safe_window=True, process_name="explorer.exe")
    # Simulate prior Win+R launch step having completed on fast path
    pipe._fast_pathed_step_ids.update({1, 2})

    type_step = PlanStep(
        step_id=3,
        intent=StepIntent.INPUT_DATA,
        description="Type text",
        success_criteria="Typed",
        status=StepStatus.IN_PROGRESS,
        directive=StepDirective(verb="TYPE", text="hello", submit=False, clear_first=True),
    )

    # Attempts 1 & 2 while still on explorer.exe / missing caret -> bounded WAIT retries
    with patch("parasite_ai.mind.dual_mind.check_caret_focus", return_value=False):
        r1 = pipe._try_directive_fast_path(type_step, wg.get_active_window(), "notepad.exe", None)
        assert r1 is not None and r1[1].action == ActionType.WAIT and r1[1].wait_ms == 1000
        assert 3 not in pipe._fast_pathed_step_ids

        r2 = pipe._try_directive_fast_path(type_step, wg.get_active_window(), "notepad.exe", None)
        assert r2 is not None and r2[1].action == ActionType.WAIT and r2[1].wait_ms == 1000
        assert 3 not in pipe._fast_pathed_step_ids

        # Retry budget exhausted (max 2) -> fails closed to VLM (None)
        assert pipe._try_directive_fast_path(type_step, wg.get_active_window(), "notepad.exe", None) is None

    # Fresh retry budget once notepad.exe + caret become ready -> dispatches TYPE with clear_first
    pipe._directive_wait_retries.clear()
    notepad_win = SimpleNamespace(title="Untitled - Notepad", process_name="notepad.exe", rect=(0, 0, 800, 600))
    with patch("parasite_ai.mind.dual_mind.check_caret_focus", return_value=True):
        r_ok = pipe._try_directive_fast_path(type_step, notepad_win, "notepad.exe", None)
        assert r_ok is not None
        assert r_ok[1].action == ActionType.TYPE
        assert r_ok[1].clear_first is True
        assert 3 in pipe._fast_pathed_step_ids
    assert brain.generate_cua_step.call_count == 0


def test_initialize_plan_attaches_win_r_directives_when_skills_enabled() -> None:
    from parasite_ai.config import SkillsConfig

    cfg = AppConfig(skills=SkillsConfig(enabled=True))
    wg = MagicMock()
    wg.is_safe_to_operate.return_value = True
    desktop_win = SimpleNamespace(title="Desktop", process_name="explorer.exe", rect=(0, 0, 1280, 720))
    wg.get_active_window.return_value = desktop_win
    wg.get_active_window_info.return_value = desktop_win

    pipe = DualMindPipeline(
        brain_manager=MagicMock(),
        mouse_driver=MagicMock(),
        keyboard_driver=MagicMock(),
        capturer=MagicMock(),
        window_guard=wg,
        config=cfg,
    )
    plan = pipe._initialize_or_update_plan("Open Paint")
    assert len(plan.steps) == 3
    assert plan.steps[0].directive is not None and plan.steps[0].directive.keys == ["win", "r"]
    assert plan.steps[1].directive is not None
    assert plan.steps[1].directive.verb == "TYPE"
    assert plan.steps[1].directive.text == "mspaint"
    assert plan.steps[1].directive.submit is True
    assert plan.steps[2].intent == StepIntent.CONCLUDE

    # When Paint is already active, do not prepend duplicate Win+R launch directives
    paint_win = SimpleNamespace(title="Untitled - Paint", process_name="mspaint.exe", rect=(0, 0, 1280, 720))
    wg.get_active_window.return_value = paint_win
    wg.get_active_window_info.return_value = paint_win
    pipe.active_plan = None
    plan_active = pipe._initialize_or_update_plan("Open Paint and draw line")
    assert all(not (s.rationale or "").startswith("launch:") for s in plan_active.steps)


def test_directive_fast_path_skips_alt_tab_and_exempts_calculator_caret() -> None:
    """P4.6.6: Skip alt+tab when target is already foreground and allow TYPE in Calculator without Win32 caret."""
    from pathlib import Path
    from parasite_ai.config import SkillsConfig
    from parasite_ai.mind.skills import SkillRegistry

    # 1. Verify data/skills/minimize-notepad/SKILL.md no longer emits an alt+tab launch step
    reg = SkillRegistry(SkillsConfig(enabled=True, skills_dir=str(Path("data/skills"))))
    reg.load_all()
    skill = reg.get("minimize-notepad")
    assert skill is not None
    assert not any(
        s.intent == StepIntent.LAUNCH_OR_ACTIVATE and [k.lower() for k in (s.keys or [])] == ["alt", "tab"]
        for s in skill.actions.steps
    )

    # 2. If any farmed plan still contains a LAUNCH_OR_ACTIVATE alt+tab, skip it when Notepad is focused
    pipe, brain, _, _ = _make_pipeline(safe_window=True, process_name="notepad.exe")
    notepad_win = SimpleNamespace(title="Untitled - Notepad", process_name="notepad.exe", rect=(0, 0, 800, 600))
    alt_tab_step = PlanStep(
        step_id=1,
        intent=StepIntent.LAUNCH_OR_ACTIVATE,
        description="Switch to Notepad",
        target_description="Notepad window",
        success_criteria="Notepad active",
        status=StepStatus.IN_PROGRESS,
        directive=StepDirective(verb="HOTKEY", keys=["alt", "tab"]),
    )
    skip_res = pipe._try_directive_fast_path(alt_tab_step, notepad_win, "Notepad", None)
    assert skip_res is not None
    assert skip_res[1].action == ActionType.WAIT
    assert skip_res[1].wait_ms == 100
    assert 1 in pipe._fast_pathed_step_ids
    assert brain.generate_cua_step.call_count == 0

    # 3. Calculator TYPE directive executes immediately without Win32 text caret
    calc_win = SimpleNamespace(title="Calculator", process_name="ApplicationFrameHost.exe", rect=(0, 0, 400, 500))
    calc_type_step = PlanStep(
        step_id=2,
        intent=StepIntent.INPUT_DATA,
        description="Enter expression",
        success_criteria="Expression entered",
        status=StepStatus.IN_PROGRESS,
        directive=StepDirective(verb="TYPE", text="15*12", submit=True),
    )
    with patch("parasite_ai.mind.dual_mind.check_caret_focus", return_value=False):
        calc_res = pipe._try_directive_fast_path(calc_type_step, calc_win, "Calculator", None)
        assert calc_res is not None
        assert calc_res[1].action == ActionType.TYPE
        assert calc_res[1].text == "15*12"

        # 4. Notepad post-wait caret exemption: 1st attempt waits, 2nd attempt dispatches TYPE
        pipe._fast_pathed_step_ids.add(1)
        np_type_step = PlanStep(
            step_id=3,
            intent=StepIntent.INPUT_DATA,
            description="Write line",
            success_criteria="Written",
            status=StepStatus.IN_PROGRESS,
            directive=StepDirective(verb="TYPE", text="Hello", submit=False),
        )
        r_wait = pipe._try_directive_fast_path(np_type_step, notepad_win, "notepad.exe", None)
        assert r_wait is not None and r_wait[1].action == ActionType.WAIT
        r_type = pipe._try_directive_fast_path(np_type_step, notepad_win, "notepad.exe", None)
        assert r_type is not None and r_type[1].action == ActionType.TYPE and r_type[1].text == "Hello"


def test_episode_plan_source_and_process_normalization() -> None:
    """P4.6.6: DualMindPipeline normalizes app names and records plan provenance."""
    assert DualMindPipeline._normalize_expected_process("Notepad") == "notepad.exe"
    assert DualMindPipeline._normalize_expected_process("Calculator") == "CalculatorApp.exe"
    assert DualMindPipeline._normalize_expected_process("calc") == "CalculatorApp.exe"
    assert DualMindPipeline._normalize_expected_process("Total: 100") is None

    pipe, _, _, wg = _make_pipeline(safe_window=True, process_name="explorer.exe")
    pipe.active_plan = None
    pipe._initialize_or_update_plan("Open Paint")
    assert pipe._episode_plan_source == "local"
    assert pipe._episode_expected_process == "mspaint.exe"

