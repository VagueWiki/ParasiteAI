"""
tests/test_dual_mind.py - Automated Unit & Integration Tests for Dual-Mind Pipeline.

Tests ActionPlan validation, ActionDispatcher target resolution, screen boundary checks,
cancellation token preemption, PersonaEngine mood transitions, and end-to-end pipeline execution.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from parasite_ai.config import AppConfig, SystemConfig, VisionConfig

from parasite_ai.mind.dual_mind import (
    ActionDispatcher,
    ActionResult,
    DualMindPipeline,
    PersonaEngine,
)
from parasite_ai.mind.memory import (
    ActionPlan,
    ActionType,
    EpisodicMemory,
)
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.types import UIElement


def test_action_plan_validation_click() -> None:
    plan = ActionPlan(action=ActionType.CLICK, target_id=3, coordinates=(100, 200))
    assert plan.action == ActionType.CLICK
    assert plan.target_id == 3
    assert plan.coordinates == (100, 200)


def test_action_plan_validation_click_and_type() -> None:
    plan = ActionPlan(
        action=ActionType.CLICK_AND_TYPE,
        target_id=2,
        text="query search\n",
        submit=True,
    )
    assert plan.action == ActionType.CLICK_AND_TYPE
    assert plan.text == "query search\n"
    assert plan.submit is True


def test_action_plan_validation_hotkey() -> None:
    plan = ActionPlan(action=ActionType.HOTKEY, keys=["ctrl", "shift", "p"])
    assert plan.action == ActionType.HOTKEY
    assert plan.keys == ["ctrl", "shift", "p"]


def test_action_dispatcher_click_by_target_id() -> None:
    mock_mouse = MagicMock()
    mock_mouse.click.return_value = True

    dispatcher = ActionDispatcher(mouse_driver=mock_mouse)

    elements = [
        UIElement.from_bbox(1, (50, 50, 100, 40), label="First"),
        UIElement.from_bbox(2, (200, 300, 100, 200), label="Second"),  # center: (250, 400)
    ]

    action = ActionPlan(action=ActionType.CLICK, target_id=2)
    res = dispatcher.dispatch(action, elements)

    assert res.success is True
    assert res.resolved_coordinates == (250, 400)
    mock_mouse.click.assert_called_once_with(
        x=250,
        y=400,
        button="left",
        clicks=1,
        cancellation_token=None,
    )


def test_action_dispatcher_click_and_type() -> None:
    mock_mouse = MagicMock()
    mock_kbd = MagicMock()
    mock_kbd.click_and_type.return_value = True

    dispatcher = ActionDispatcher(mouse_driver=mock_mouse, keyboard_driver=mock_kbd)

    elements = [
        UIElement.from_bbox(1, (100, 150, 200, 50), label="SearchInput", role="Edit"),
    ]

    action = ActionPlan(
        action=ActionType.CLICK_AND_TYPE,
        target_id=1,
        text="ParasiteAI",
        submit=True,
    )
    res = dispatcher.dispatch(action, elements)

    assert res.success is True
    assert res.resolved_coordinates == (200, 175)
    mock_kbd.click_and_type.assert_called_once_with(
        x=200,
        y=175,
        text="ParasiteAI",
        submit=True,
        cancellation_token=None,
        mouse_driver=mock_mouse,
        clear_first=True,
    )


def test_action_dispatcher_out_of_bounds_rejection() -> None:
    mock_mouse = MagicMock()
    dispatcher = ActionDispatcher(mouse_driver=mock_mouse)

    # Force validate_coordinates to return False for extreme coordinate
    dispatcher.validate_coordinates = MagicMock(return_value=False)

    action = ActionPlan(action=ActionType.CLICK, coordinates=(999999, 999999))
    res = dispatcher.dispatch(action, [])

    assert res.success is False
    assert "out of desktop bounds" in (res.error or "")
    mock_mouse.click.assert_not_called()


def test_action_dispatcher_cancellation_preemption() -> None:
    mock_mouse = MagicMock()
    mock_kbd = MagicMock()
    dispatcher = ActionDispatcher(mouse_driver=mock_mouse, keyboard_driver=mock_kbd)

    token = threading.Event()
    token.set()  # Pre-set cancellation token

    action = ActionPlan(action=ActionType.CLICK, coordinates=(100, 100))
    res = dispatcher.dispatch(action, [], cancellation_token=token)

    assert res.success is False
    assert res.interrupted is True
    mock_mouse.click.assert_not_called()
    mock_mouse.release_all_buttons.assert_called_once()


def test_persona_engine_monologue_and_mood() -> None:
    mock_brain = MagicMock()
    mock_brain.generate_thought.return_value = (
        "<thought>Looking at the login screen. I see username and password fields.</thought>"
        "I'll enter your credentials now!"
    )

    bridge = MagicMock()
    engine = PersonaEngine(brain_manager=mock_brain, bridge=bridge)

    out = engine.generate_monologue(
        user_goal="Login to app",
        scene_summary="Login dialog visible",
        memory_context="No prior actions",
        mood_override="Focused",
    )

    assert "Looking at the login screen" in out.thought
    assert "I'll enter your credentials now!" in out.speech
    assert out.mood == "Focused"
    bridge.notify_thought.assert_called_once_with(out.thought)
    bridge.notify_speech.assert_called_once_with(out.speech)


def test_persona_engine_mood_derivation_on_strikes() -> None:
    engine = PersonaEngine(brain_manager=MagicMock())
    mem = EpisodicMemory()

    # Default idle
    assert engine.derive_mood(mem, state="WATCHING") == "Curious"

    # Driving action
    assert engine.derive_mood(mem, state="DRIVING") == "Focused"

    # 2 strikes -> Cautious
    mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=True, screen_diff=0.001)
    mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=True, screen_diff=0.001)
    assert engine.derive_mood(mem, state="WATCHING") == "Cautious"

    # 3 strikes -> Panic-Averted
    mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=True, screen_diff=0.001)
    assert engine.derive_mood(mem, state="WATCHING") == "Panic-Averted"


def test_dual_mind_pipeline_end_to_end_step() -> None:
    mock_brain = MagicMock()
    mock_brain.generate_thought.return_value = "Observing button. Clicking submit."
    mock_brain.generate_action.return_value = {
        "action": "CLICK",
        "target_id": 1,
        "reasoning": "Clicking submit button",
    }

    mock_mouse = MagicMock()
    mock_mouse.click.return_value = True

    bridge = MagicMock()
    mem = EpisodicMemory()

    pipeline = DualMindPipeline(
        brain_manager=mock_brain,
        memory=mem,
        mouse_driver=mock_mouse,
        bridge=bridge,
    )

    elements = [
        UIElement.from_bbox(1, (100, 100, 80, 30), label="Submit", role="Button"),
    ]
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    rec = pipeline.step(
        user_goal="Click submit",
        screen_frame=frame,
        grounded_elements=elements,
    )

    assert rec.step_id == 1
    assert rec.action.action == ActionType.CLICK
    assert rec.action.target_id == 1
    assert rec.success is True
    mock_mouse.click.assert_called_once()
    bridge.set_hud_targets.assert_called_once_with(elements)


def test_dual_mind_pipeline_sensitive_window_pause() -> None:
    mock_window_guard = MagicMock()
    mock_window_guard.is_safe_to_operate.return_value = False

    bridge = MagicMock()
    mem = EpisodicMemory()

    pipeline = DualMindPipeline(
        brain_manager=MagicMock(),
        memory=mem,
        window_guard=mock_window_guard,
        bridge=bridge,
    )

    rec = pipeline.step(user_goal="Test goal")

    assert rec.success is False
    assert "Sensitive window" in (rec.error_message or "")
    bridge.notify_state.assert_called_with("PROTECTED", "Cautious")


def test_dual_mind_pipeline_interrupt_guard_override() -> None:
    mock_interrupt_guard = MagicMock()
    mock_interrupt_guard.is_interrupted.return_value = True

    bridge = MagicMock()
    mem = EpisodicMemory()

    pipeline = DualMindPipeline(
        brain_manager=MagicMock(),
        memory=mem,
        interrupt_guard=mock_interrupt_guard,
        bridge=bridge,
    )

    rec = pipeline.step(user_goal="Test goal")

    assert rec.success is False
    assert "User override active" in (rec.error_message or "")
    bridge.notify_state.assert_called_with("USER_OVERRIDE", "Curious")


def test_dual_mind_pipeline_loop_break_strategy() -> None:
    mock_brain = MagicMock()
    mock_brain.generate_thought.return_value = "Stuck in a loop."
    # Even if LLM returns normal action:
    mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}

    mem = EpisodicMemory(strike_limit=3)
    # Trip 3 strikes
    mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=True, screen_diff=0.001)
    mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=True, screen_diff=0.001)
    mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=True, screen_diff=0.001)
    assert mem.is_in_loop() is True

    bridge = MagicMock()
    pipeline = DualMindPipeline(
        brain_manager=mock_brain,
        memory=mem,
        bridge=bridge,
    )

    rec = pipeline.step(user_goal="Try again")
    # Loop detector overrides action with PANIC
    assert rec.action.action == ActionType.PANIC
    bridge.sig_panic_triggered.emit.assert_called_once()


def test_dual_mind_pipeline_done_action() -> None:
    mock_brain = MagicMock()
    mock_brain.generate_thought.return_value = "Goal accomplished."

    bridge = MagicMock()
    mem = EpisodicMemory()
    pipeline = DualMindPipeline(
        brain_manager=mock_brain,
        memory=mem,
        bridge=bridge,
    )

    rec = pipeline.step(
        user_goal="Finish task",
        override_action=ActionPlan(action=ActionType.DONE, reasoning="Completed"),
    )

    assert rec.action.action == ActionType.DONE
    assert rec.success is True
    bridge.notify_state.assert_called_with("WATCHING", "Amused")
    bridge.clear_hud_targets.assert_called_once()


def test_action_dispatcher_type_with_cua_mode_relaxes_caret_guard() -> None:
    """Verifies cua_mode=True bypasses Win32 caret check and executes typing directly."""
    mock_mouse = MagicMock()
    mock_keyboard = MagicMock()
    mock_keyboard.type_text.return_value = True

    dispatcher = ActionDispatcher(mouse_driver=mock_mouse, keyboard_driver=mock_keyboard)
    # verify_caret_focus returns False
    dispatcher.verify_caret_focus = MagicMock(return_value=False)

    action = ActionPlan(action=ActionType.TYPE, text="hello world", submit=False)

    # 1. cua_mode=False fails with 'Caret focus not detected'
    res_fail = dispatcher.dispatch(action=action, som_elements=[], cua_mode=False)
    assert res_fail.success is False
    assert "Caret focus not detected" in (res_fail.error or "")
    mock_keyboard.type_text.assert_not_called()

    # 2. cua_mode=True succeeds and calls keyboard driver
    res_ok = dispatcher.dispatch(action=action, som_elements=[], cua_mode=True)
    assert res_ok.success is True
    assert res_ok.error is None
    mock_keyboard.type_text.assert_called_once_with(
        text="hello world",
        submit=False,
        cancellation_token=None,
    )


def test_action_dispatcher_type_exempts_shell_and_uwp_processes() -> None:
    """Verifies StartMenuExperienceHost and SearchApp are exempt from caret check even without cua_mode."""
    mock_mouse = MagicMock()
    mock_keyboard = MagicMock()
    mock_keyboard.type_text.return_value = True

    dispatcher = ActionDispatcher(mouse_driver=mock_mouse, keyboard_driver=mock_keyboard)
    dispatcher.verify_caret_focus = MagicMock(return_value=False)

    action = ActionPlan(action=ActionType.TYPE, text="notepad\n", submit=True)
    elem = UIElement(
        id=1,
        role="Edit",
        name="Search",
        process_name="StartMenuExperienceHost.exe",
        window_title="Search",
        is_active_window=True,
        x=10,
        y=10,
        width=100,
        height=30,
        center_x=60,
        center_y=25,
    )

    res = dispatcher.dispatch(action=action, som_elements=[elem], cua_mode=False)
    assert res.success is True
    assert res.error is None
    mock_keyboard.type_text.assert_called_once_with(
        text="notepad\n",
        submit=True,
        cancellation_token=None,
    )


def test_dual_mind_cua_bypasses_heuristics_and_suppresses_tier_2_browser() -> None:
    """Verifies CUA mode executes VLM plan directly without post-inference heuristic corruption or browser launches."""
    from parasite_ai.mind.memory import CadenceTier

    mock_brain = MagicMock()
    mock_brain.supports_vision.return_value = True
    # generate_cua_step returns TYPE with submit=True and custom reasoning
    cua_action = ActionPlan(
        action=ActionType.TYPE,
        text="test.txt",
        submit=True,
        reasoning="Type filename into Save As dialog",
    )
    mock_brain.generate_cua_step.return_value = ("Typing filename", cua_action)

    mock_offloader = MagicMock()
    mock_keyboard = MagicMock()
    mock_keyboard.type_text.return_value = True
    mock_mouse = MagicMock()

    dispatcher = ActionDispatcher(mouse_driver=mock_mouse, keyboard_driver=mock_keyboard)
    dispatcher.verify_caret_focus = MagicMock(return_value=False)

    pipeline = DualMindPipeline(
        brain_manager=mock_brain,
        offloader=mock_offloader,
        mouse_driver=mock_mouse,
        keyboard_driver=mock_keyboard,
        config=None,
    )
    pipeline.action_dispatcher = dispatcher
    # Simulate tier escalated to TIER_2_CONSULT
    pipeline.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
    pipeline.escalation_sm.local_strikes = 3

    test_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    # Goal contains 'type note' which historically triggered [DOCUMENT TARGET REDIRECT] and submit=False
    rec = pipeline.step(
        user_goal="type note filename test.txt and press enter",
        screen_frame=test_frame,
    )

    # 1. Tier 2 browser offloader was NOT invoked
    mock_offloader.query_web_ai.assert_not_called()
    assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL

    # 2. CUA step was invoked with image_base64=None so BrainManager uses uncropped frame
    mock_brain.generate_cua_step.assert_called_once()
    cua_call_kwargs = mock_brain.generate_cua_step.call_args.kwargs
    assert cua_call_kwargs["image_base64"] is None
    assert cua_call_kwargs["screen_frame"] is test_frame

    # 3. Action plan submit remained True (heuristic did NOT overwrite it)
    assert rec.action.submit is True
    assert rec.action.text == "test.txt"
    assert rec.success is True


def test_dual_mind_cua_suppresses_hud_targets_to_avoid_vision_obfuscation():
    """In CUA mode, set_hud_targets is suppressed so GhostHUD does not paint SoM boxes over UI-TARS's vision."""
    mock_brain = MagicMock()
    mock_brain.supports_vision = MagicMock(return_value=True)
    mock_brain.generate_cua_step.return_value = (
        "Click Start",
        ActionPlan(action=ActionType.CLICK, coordinates=[24, 980]),
    )
    mock_bridge = MagicMock()
    mock_mouse = MagicMock()
    mock_keyboard = MagicMock()

    pipeline = DualMindPipeline(
        brain_manager=mock_brain,
        mouse_driver=mock_mouse,
        keyboard_driver=mock_keyboard,
        bridge=mock_bridge,
    )

    test_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    fake_element = UIElement(
        id=1, label="Start", role="Button", x=24, y=980, width=40, height=40, center_x=44, center_y=1000
    )

    pipeline.step(
        user_goal="Open Start Menu",
        screen_frame=test_frame,
        grounded_elements=[fake_element],
    )

    # In CUA mode, set_hud_targets is suppressed
    mock_bridge.set_hud_targets.assert_not_called()
    # But notify_perception is still called for dock thumbnail preview
    mock_bridge.notify_perception.assert_called_once_with(test_frame, [fake_element])


def test_get_effective_active_window_skips_relocate_non_target_monitor2() -> None:
    """
    Stint P4.1.1: Monitor-2 windows that are not the current goal's TARGET (e.g. chrome_widgetwin_1)
    must remain undisturbed on Monitor 2 while _get_effective_active_window falls back to Monitor 1.
    Actual TARGET apps on Monitor 2 (e.g. Calculator) are still relocated onto Monitor 1.
    """
    cfg = AppConfig(vision=VisionConfig(monitor_index=1))
    mock_guard = MagicMock()
    pipeline = DualMindPipeline(
        brain_manager=MagicMock(),
        mouse_driver=MagicMock(),
        keyboard_driver=MagicMock(),
        window_guard=mock_guard,
        config=cfg,
    )

    with (
        patch("parasite_ai.vision.capture.get_monitor_bounds", return_value=(0, 0, 1920, 1080)),
        patch("parasite_ai.mind.dual_mind.relocate_window_to_monitor", return_value=True) as mock_relocate,
    ):
        # 1. Stray browser/Electron window on Monitor 2 (cx=2880) during Calculator task -> NOT relocated
        mock_guard.get_active_window.return_value = SimpleNamespace(
            title="chrome_widgetwin_1",
            process_name="chrome.exe",
            rect=(2200, 100, 3560, 900),
            hwnd=198014,
        )
        eff_non_target = pipeline._get_effective_active_window(user_goal="Open Calculator and compute 7 * 8")
        mock_relocate.assert_not_called()
        assert eff_non_target.rect == (0, 0, 1920, 1080)
        assert eff_non_target.title == "Desktop"

        # 1b. Explicit empty user_goal="" also does NOT relocate Monitor-2 windows
        eff_empty_goal = pipeline._get_effective_active_window(user_goal="")
        mock_relocate.assert_not_called()
        assert eff_empty_goal.rect == (0, 0, 1920, 1080)

        # 2. Actual TARGET app (Calculator) on Monitor 2 -> IS relocated to Monitor 1
        mock_guard.get_active_window.return_value = SimpleNamespace(
            title="Calculator",
            process_name="ApplicationFrameHost.exe",
            rect=(2200, 120, 2700, 720),
            hwnd=204010,
        )
        eff_target = pipeline._get_effective_active_window(user_goal="Open Calculator and compute 7 * 8")
        mock_relocate.assert_called_once_with(204010, 1)
        assert eff_target.title == "Calculator"
        assert eff_target.rect[0] == 100


def test_dual_mind_vlm_micro_glance_gated_by_config() -> None:
    """
    Stint P4.1.1: Tier-2 VLM micro-glance is gated behind VisionConfig.enable_vlm_micro_glance
    (default False) so CUA mode never incurs 1024-token VLM latency spikes unprompted.
    """
    mock_brain = MagicMock()
    mock_brain.supports_vision.return_value = True
    crop = np.zeros((128, 128, 3), dtype=np.uint8)

    default_pipeline = DualMindPipeline(
        brain_manager=mock_brain,
        mouse_driver=MagicMock(),
        keyboard_driver=MagicMock(),
        config=AppConfig(vision=VisionConfig(enable_vlm_micro_glance=False)),
    )
    assert default_pipeline.action_dispatcher.vlm_glance_fn is None
    assert default_pipeline._vlm_micro_glance(crop, "7") == ""
    mock_brain.generate.assert_not_called()

    enabled_pipeline = DualMindPipeline(
        brain_manager=mock_brain,
        mouse_driver=MagicMock(),
        keyboard_driver=MagicMock(),
        config=AppConfig(vision=VisionConfig(enable_vlm_micro_glance=True)),
    )
    assert enabled_pipeline.action_dispatcher.vlm_glance_fn == enabled_pipeline._vlm_micro_glance


def test_dual_mind_saves_step_screenshots_when_enabled(tmp_path) -> None:
    """Stint P4.1.2: Verifies DualMindPipeline.step() writes step_01_pre.jpg when save_debug_screenshots=True."""
    mock_brain = MagicMock()
    mock_brain.supports_vision.return_value = True
    mock_brain.generate_cua_step.return_value = (
        "Click Start button",
        ActionPlan(action=ActionType.CLICK, coordinates=(40, 100)),
    )
    mock_mouse = MagicMock()
    mock_mouse.click.return_value = True

    cfg = AppConfig(system=SystemConfig(data_dir=tmp_path, save_debug_screenshots=True, max_screenshot_episodes=5))
    pipeline = DualMindPipeline(
        brain_manager=mock_brain,
        mouse_driver=mock_mouse,
        keyboard_driver=MagicMock(),
        config=cfg,
    )
    pipeline.start_debug_episode("Open Calculator")

    test_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    raw_copy = test_frame.copy()
    pipeline.step(user_goal="Open Calculator", screen_frame=test_frame, grounded_elements=[])

    assert np.array_equal(test_frame, raw_copy)
    ep_dir = pipeline.screenshot_recorder.current_episode_dir
    assert ep_dir is not None
    assert (ep_dir / "step_01_pre.jpg").exists()


def test_dual_mind_executes_burst_action_sequence_in_cua_mode() -> None:
    """Stint P4.2: Verifies DualMindPipeline.step() dispatches compound BURST actions end-to-end."""
    mock_brain = MagicMock()
    mock_brain.supports_vision.return_value = True

    sub_plans = [
        ActionPlan(action=ActionType.CLICK, coordinates=(100, 100)),
        ActionPlan(action=ActionType.CLICK, coordinates=(150, 100)),
        ActionPlan(action=ActionType.CLICK, coordinates=(200, 100)),
    ]
    burst_plan = ActionPlan(
        action=ActionType.BURST,
        burst_actions=sub_plans,
        reasoning="Keypad reflex burst",
    )
    mock_brain.generate_cua_step.return_value = ("Calculating 7 * 8", burst_plan)

    mock_mouse = MagicMock()
    mock_mouse.click.return_value = True

    pipeline = DualMindPipeline(
        brain_manager=mock_brain,
        mouse_driver=mock_mouse,
        keyboard_driver=MagicMock(),
        config=None,
    )

    test_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    rec = pipeline.step(user_goal="Calculate 7 * 8", screen_frame=test_frame, grounded_elements=[])

    assert rec.action.action == ActionType.BURST
    assert rec.success is True
    assert mock_mouse.click.call_count == 3
    # Check that StepRecord telemetry captured burst
    summary = rec.to_summary()
    assert summary.action_type == "BURST"
    assert summary.burst_count == 3



