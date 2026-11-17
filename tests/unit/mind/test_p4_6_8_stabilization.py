"""Unit tests for Stint P4.6.8 (0.4.6.8) L2/L3 unblock & CUA stabilization fixes."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from parasite_ai.mind.affordance import ActionAffordance
from parasite_ai.mind.dual_mind import DualMindPipeline, should_trigger_proactive_plan
from parasite_ai.mind.memory import ActionPlan, ActionType, CadenceTier, EpisodicMemory
from parasite_ai.mind.uitars_parser import parse_uitars_action


def test_uitars_parser_deduplicates_degenerate_multiline_type():
    raw = (
        "Thought: Typing greeting.\n"
        "Action: type(content='Hello! How can I assist you today?')\n\n"
        + "\n\n".join(["type(content='Hello! How can I assist you today?')"] * 10)
    )
    _, plan = parse_uitars_action(raw, screen_width=1920, screen_height=1080)
    assert plan.action == ActionType.TYPE
    assert plan.text == "Hello! How can I assist you today?"


def test_cua_keyboard_burst_credited_without_false_strike():
    mouse = MagicMock()
    keyboard = MagicMock()
    keyboard.type_text.return_value = True
    keyboard.hotkey.return_value = True

    capturer = MagicMock()
    pre = np.zeros((1080, 1920, 3), dtype=np.uint8)
    post = pre.copy()
    post[10:20, 10:20] = 255  # < 0.001 screen diff (like Calculator digits)
    capturer.capture_screen.side_effect = [pre, post]

    grounder = MagicMock()
    grounder.ground_elements.return_value = []

    brain = MagicMock()
    brain.is_running = True
    brain.generate_cua_step.return_value = parse_uitars_action(
        "Thought: Compute 144 / 12.\nAction: type(content='144/12')\n\nhotkey(key='enter')"
    )

    pipeline = DualMindPipeline(
        brain_manager=brain,
        memory=EpisodicMemory(),
        mouse_driver=mouse,
        keyboard_driver=keyboard,
        screen_grounder=grounder,
        capturer=capturer,
    )
    pipeline._is_cua_mode_active = lambda override_action=None: True
    pipeline.step(user_goal="Open Calculator, compute 144 / 12")
    assert pipeline.escalation_sm.local_strikes == 0
    assert pipeline.escalation_sm.current_tier == CadenceTier.TIER_1_LOCAL


def test_consecutive_idle_waits_trigger_stagnation_strike():
    mouse = MagicMock()
    keyboard = MagicMock()
    capturer = MagicMock()
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    capturer.capture_screen.return_value = frame

    grounder = MagicMock()
    grounder.ground_elements.return_value = []

    brain = MagicMock()
    brain.is_running = True
    brain.generate_cua_step.return_value = ("Still loading.", ActionPlan(action=ActionType.WAIT, reasoning="Still loading."))

    pipeline = DualMindPipeline(
        brain_manager=brain,
        memory=EpisodicMemory(),
        mouse_driver=mouse,
        keyboard_driver=keyboard,
        screen_grounder=grounder,
        capturer=capturer,
    )
    pipeline._is_cua_mode_active = lambda override_action=None: True
    pipeline.step(user_goal="Open Chrome, go to https://example.com")
    pipeline.step(user_goal="Open Chrome, go to https://example.com")
    assert pipeline.escalation_sm.local_strikes == 0

    pipeline.step(user_goal="Open Chrome, go to https://example.com")
    assert pipeline._consecutive_idle_waits == 3
    assert pipeline.escalation_sm.local_strikes == 1


def test_should_trigger_proactive_plan_skips_single_window_close():
    ps = MagicMock()
    ps.is_available.return_value = True
    ps.config = MagicMock(proactive_planning=True, proactive_mode="open_ended")

    assert (
        should_trigger_proactive_plan(
            user_goal="Close Notepad",
            target_app=None,
            affordance=ActionAffordance.PHYSICAL_GUI,
            has_active_skill=False,
            parasite_skill=ps,
        )
        is False
    )
    assert (
        should_trigger_proactive_plan(
            user_goal="Open Chrome, go to https://example.com, and write heading into Notepad",
            target_app="chrome",
            affordance=ActionAffordance.PHYSICAL_GUI,
            has_active_skill=False,
            parasite_skill=ps,
        )
        is True
    )
