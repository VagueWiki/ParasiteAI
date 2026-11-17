"""Unit tests for Stint P4.6.7 (0.4.6.7) benchmark stabilization & telemetry fixes."""

from __future__ import annotations

import json
import types
from unittest.mock import MagicMock

import numpy as np

from parasite_ai.mind.dual_mind import DualMindPipeline
from parasite_ai.mind.memory import ActionPlan, ActionType, CadenceTier, EpisodicMemory, StepRecordSummary
from parasite_ai.mind.parasite_protocol import ParasiteFailure, ParasitePhase, parse_response
from parasite_ai.mind.parasite_skill import ParasiteSkill
from parasite_ai.mind.plan import PlanStep, StepDirective, StepIntent
from parasite_ai.mind.uitars_parser import parse_uitars_action
from parasite_ai.runtime import RuntimeOrchestrator


def test_uitars_parser_drag_and_multiline_actions():
    thought, drag_plan = parse_uitars_action(
        "Thought: Highlight text.\nAction: drag(start_box='(324,127)', end_box='(407,128)')",
        screen_width=1920,
        screen_height=1080,
    )
    assert drag_plan.action == ActionType.DRAG
    assert drag_plan.coordinates == (324, 127)
    assert drag_plan.end_coordinates == (407, 128)

    _, multi_plan = parse_uitars_action(
        "Thought: Multiply and press enter.\nAction: type(content='*4')\n\nhotkey(key='enter')",
        screen_width=1920,
        screen_height=1080,
    )
    assert multi_plan.action == ActionType.BURST
    assert multi_plan.burst_actions is not None
    assert len(multi_plan.burst_actions) == 2
    assert multi_plan.burst_actions[0].action == ActionType.TYPE
    assert multi_plan.burst_actions[0].text == "*4"
    assert multi_plan.burst_actions[1].action == ActionType.HOTKEY
    assert multi_plan.burst_actions[1].keys == ["enter"]


def test_parse_response_strips_markdown_urls():
    nonce = "abc12345"
    plan_payload = {
        "selected_program": "chrome.exe",
        "rationale": "Open site",
        "steps": [
            {
                "intent": "LAUNCH_OR_ACTIVATE",
                "description": "Open Chrome with URL",
                "target_description": "Run dialog",
                "tool_route": "GUI",
                "success_criteria": "Chrome opens",
                "action": {
                    "verb": "TYPE",
                    "text": "chrome [https://example.com](https://example.com)",
                    "keys": ["enter"],
                    "submit": True,
                },
            }
        ],
    }
    raw = f'<parasite_plan nonce="{nonce}">\n{json.dumps(plan_payload)}\n</parasite_plan>'
    parsed = parse_response(raw, nonce=nonce, phase=ParasitePhase.PROACTIVE_PLAN)
    assert not isinstance(parsed, ParasiteFailure)
    assert parsed.plan is not None
    assert parsed.plan.steps[0].action.text == "chrome https://example.com"


def test_parasite_skill_press_pagedown_scrolls_pane():
    mouse = MagicMock()
    mouse.scroll.return_value = True
    keyboard = MagicMock()
    keyboard.hotkey.return_value = True
    skill = ParasiteSkill.__new__(ParasiteSkill)
    skill.mouse = mouse
    skill.keyboard = keyboard
    skill.config = MagicMock()
    ok = skill._press_pagedown(win_rect=(1000, 100, 1900, 900))
    assert ok is True
    mouse.scroll.assert_called_once()
    args, kwargs = mouse.scroll.call_args
    assert args[0] == -5
    assert 1000 < kwargs["x"] < 1900
    assert 100 < kwargs["y"] < 900
    keyboard.hotkey.assert_called_once_with("pagedown", cancellation_token=None)


def test_dual_mind_fast_path_blocks_launch_type_outside_shell():
    pipeline = DualMindPipeline(brain_manager=MagicMock(), memory=EpisodicMemory())
    step = PlanStep(
        step_id=3,
        description="Launch notepad",
        intent=StepIntent.LAUNCH_OR_ACTIVATE,
        success_criteria="Notepad opens",
        directive=StepDirective(verb="TYPE", text="notepad", submit=True),
    )
    active_win = types.SimpleNamespace(process_name="ApplicationFrameHost.exe", title="Calculator")
    res = pipeline._try_directive_fast_path(
        step=step,
        active_window=active_win,
        expected_process="calc.exe",
        token=None,
    )
    assert res is None
    assert pipeline._episode_fast_path_abort_reason == "step_3_launch_type_non_shell:applicationframehost.exe"


def test_dual_mind_drag_dispatch_and_veto_loop_telemetry():
    mouse = MagicMock()
    mouse.drag_and_drop.return_value = True
    keyboard = MagicMock()
    capturer = MagicMock()
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    capturer.capture_screen.return_value = frame

    grounder = MagicMock()
    grounder.ground_elements.return_value = []

    brain = MagicMock()
    brain.is_running = True
    brain.analyze_screen.return_value = (
        "Thought: Task finished.\nAction: finished()"
    )
    brain.generate_persona.return_value = "Thought: Task finished."
    brain.generate_action.return_value = {"action": "DONE", "reasoning": "Task finished."}

    pipeline = DualMindPipeline(
        brain_manager=brain,
        memory=EpisodicMemory(),
        mouse_driver=mouse,
        keyboard_driver=keyboard,
        screen_grounder=grounder,
        capturer=capturer,
    )

    drag_res = pipeline.action_dispatcher.dispatch(
        ActionPlan(action=ActionType.DRAG, coordinates=(300, 120), end_coordinates=(420, 120)),
        som_elements=[],
        frame=frame,
    )
    assert drag_res.success is True
    mouse.drag_and_drop.assert_called_once_with(300, 120, 420, 120, cancellation_token=None)

    # Repeated Pre-DONE veto should increment veto_count and trigger a failure strike on 2nd consecutive veto
    pipeline.goal_verifier = MagicMock()
    pipeline.goal_verifier.verify_goal_state.return_value = types.SimpleNamespace(
        verified=False, reason="Target file new_name.txt does not exist on disk yet"
    )
    pipeline.step(user_goal="Rename old_name.txt to new_name.txt")
    assert pipeline._episode_veto_count == 1
    assert pipeline.escalation_sm.local_strikes == 0

    pipeline.step(user_goal="Rename old_name.txt to new_name.txt")
    assert pipeline._episode_veto_count == 2
    assert pipeline.escalation_sm.local_strikes == 1


def test_runtime_episode_receipt_includes_veto_and_fast_path_telemetry(tmp_path):
    app_mem = MagicMock()
    pipeline = MagicMock()
    pipeline.start_debug_episode.return_value = None
    pipeline._episode_plan_source = "proactive_gemini"
    pipeline._episode_skill_id = None
    pipeline._episode_farmed_plan_id = 16
    pipeline._episode_fast_path_steps = 2
    pipeline._episode_parasite_invocations = 1
    pipeline._episode_parasite_status = "OK"
    pipeline._episode_veto_count = 3
    pipeline._episode_fast_path_abort_reason = "step_3_launch_type_non_shell:applicationframehost.exe"
    pipeline.escalation_sm.current_tier = CadenceTier.TIER_1_LOCAL
    pipeline.step.return_value = types.SimpleNamespace(
        action=ActionPlan(action=ActionType.DONE, reasoning="done"),
        action_plan=ActionPlan(action=ActionType.DONE, reasoning="done"),
        success=True,
        action_result=types.SimpleNamespace(success=True, error=None, resolved_coordinates=None),
        screen_diff=0.0,
        tier=CadenceTier.TIER_1_LOCAL,
        step_duration=0.01,
        thought="done",
        had_human_override=False,
        to_summary=lambda duration_sec=0.01: StepRecordSummary(
            step_id=1,
            action_type=ActionType.DONE,
            screen_diff=0.0,
            success=True,
            duration_sec=duration_sec,
        ),
    )

    rt = RuntimeOrchestrator.__new__(RuntimeOrchestrator)
    rt._is_paused = False
    rt.simulation_mode = True
    rt._step_interrupted_latched = False
    rt._is_in_cognitive_step = False
    rt.config = types.SimpleNamespace(
        skills=types.SimpleNamespace(enabled=False),
        system=types.SimpleNamespace(auto_exit_on_complete=False),
    )
    rt.pipeline = pipeline
    rt.memory = EpisodicMemory()
    rt.bridge = MagicMock()
    rt.interrupt_guard = MagicMock()
    rt.interrupt_guard.is_panic.return_value = False
    rt.interrupt_guard.is_interrupted.return_value = False
    rt.interrupt_guard.interrupt_count = 0
    rt.window_guard = None
    rt.app_memory = app_mem
    rt.episode_report_path = str(tmp_path / "receipt.json")
    rt._stop_event = MagicMock()
    rt._stop_event.is_set.return_value = False
    rt._skill_lock = MagicMock()
    rt.last_episode_receipt = None

    receipt = rt.run_goal_sync("test goal", max_steps=5)
    assert receipt.success is True
    assert receipt.veto_count == 3
    assert receipt.fast_path_abort_reason == "step_3_launch_type_non_shell:applicationframehost.exe"
    app_mem.record_episode.assert_called_once()
    _, kwargs = app_mem.record_episode.call_args
    assert isinstance(kwargs["duration_sec"], float)
