"""
tests/test_dual_mind.py - Automated Unit & Integration Tests for Dual-Mind Pipeline.

Tests ActionPlan validation, ActionDispatcher target resolution, screen boundary checks,
cancellation token preemption, PersonaEngine mood transitions, and end-to-end pipeline execution.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock
import numpy as np
import pytest

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
