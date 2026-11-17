"""Targeted unit tests for Stint P4.7.4 (0.4.7.4) Pre-DONE veto feedback and prompt-echo checklist guard."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from parasite_ai.config import AppConfig
from parasite_ai.mind.dual_mind import ActionResult, DualMindPipeline
from parasite_ai.mind.memory import ActionPlan, ActionType, EpisodicMemory
from parasite_ai.mind.uitars_parser import UITARS_SYSTEM_PROMPT
from parasite_ai.mind.verifier import GoalVerificationResult, RuntimeGoalVerifier

pytestmark = pytest.mark.unit


def test_pre_done_veto_populates_cua_loop_warning_and_clears_on_productive_type() -> None:
    cfg = AppConfig()
    brain = MagicMock()
    brain.supports_vision.return_value = True
    brain.generate_cua_step.return_value = (
        "Looks done.",
        ActionPlan(action=ActionType.DONE, reasoning="Done"),
    )
    pipe = DualMindPipeline(brain_manager=brain, memory=EpisodicMemory(), config=cfg)
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    with patch.object(
        pipe.goal_verifier,
        "verify_goal_state",
        return_value=GoalVerificationResult(
            verified=False,
            reason="Notepad composed text is too short or lacks sentence punctuation.",
            checked_conditions=["notepad_greeting_composed"],
        ),
    ), patch.object(
        pipe.goal_verifier,
        "build_working_memory_snapshot",
        return_value="- Active Window: Untitled - Notepad (notepad.exe)",
    ), patch.object(
        pipe.action_dispatcher,
        "dispatch",
        return_value=ActionResult(success=True, action_executed=ActionPlan(action=ActionType.WAIT)),
    ):
        rec1 = pipe.step(
            user_goal="Open Notepad and write a 2-sentence overview of desktop automation",
            screen_frame=frame,
            grounded_elements=[],
        )

    assert rec1.action.action == ActionType.WAIT
    assert pipe._cua_loop_warning is not None
    assert "Premature finished() rejected" in pipe._cua_loop_warning

    # Next step should inject Loop Intervention Warning into working_memory_context and clear it after productive TYPE
    brain.generate_cua_step.return_value = (
        "Wait, let me write prose.",
        ActionPlan(
            action=ActionType.TYPE,
            text="Automation runs UI tasks visibly. It verifies outcomes.",
            reasoning="Write prose",
        ),
    )
    with patch.object(
        pipe.goal_verifier,
        "build_working_memory_snapshot",
        return_value="- Active Window: *Untitled - Notepad (notepad.exe)",
    ), patch.object(
        pipe.action_dispatcher,
        "dispatch",
        return_value=ActionResult(
            success=True,
            action_executed=ActionPlan(
                action=ActionType.TYPE,
                text="Automation runs UI tasks visibly. It verifies outcomes.",
            ),
        ),
    ), patch("parasite_ai.mind.dual_mind.compute_pixel_diff", return_value=0.05):
        rec2 = pipe.step(
            user_goal="Open Notepad and write a 2-sentence overview of desktop automation",
            screen_frame=frame,
            grounded_elements=[],
        )

    assert rec2.action.action == ActionType.TYPE
    second_call_kwargs = brain.generate_cua_step.call_args_list[1].kwargs
    assert "Loop Intervention Warning: Premature finished() rejected" in second_call_kwargs["working_memory_context"]
    assert pipe._cua_loop_warning is None


def test_goal_verifier_checklist_rejects_prompt_echo_and_explains_incomplete_text() -> None:
    verifier = RuntimeGoalVerifier()
    windows = [
        {
            "hwnd": 100,
            "title": "*Untitled - Notepad",
            "class_name": "Notepad",
            "pid": 4321,
            "process_name": "notepad.exe",
            "is_minimized": False,
            "rect": (50, 50, 850, 650),
        }
    ]
    goal = "Open Notepad and write a 2-sentence overview of desktop automation"

    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=windows), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value="A 2-sentence overview of desktop automation."):
        snap = verifier.build_working_memory_snapshot(user_goal=goal)

    assert "[x] Launch Notepad" in snap
    assert "[ ] Compose text in Notepad (current text is too short, lacks sentence punctuation, or echoes the prompt)" in snap
    assert "All derived sub-goals are satisfied [x]" not in snap


def test_uitars_system_prompt_generative_rule_uses_abstract_placeholders() -> None:
    assert "GENERATIVE WRITING TASKS" in UITARS_SYSTEM_PROMPT
    assert "<sentence 1>. <sentence 2>." in UITARS_SYSTEM_PROMPT
    assert "<N> sentences about <topic>" in UITARS_SYSTEM_PROMPT
    assert "A brief overview of" not in UITARS_SYSTEM_PROMPT


def test_goal_verifier_rejects_multi_sentence_meta_outline_boilerplate() -> None:
    verifier = RuntimeGoalVerifier()
    windows = [
        {
            "hwnd": 100,
            "title": "*Untitled - Notepad",
            "class_name": "Notepad",
            "pid": 4321,
            "process_name": "notepad.exe",
            "is_minimized": False,
            "rect": (50, 50, 850, 650),
        }
    ]
    goal = "Open Notepad and write a 2-sentence overview of desktop automation"
    boilerplate = (
        "A brief overview of desktop automation. "
        "The first sentence is about the basic operations, and the second sentence is about the advanced features."
    )
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=windows), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value=boilerplate):
        res = verifier.verify_goal_state(goal)
        assert res.verified is False
        assert "notepad_greeting_non_echo" in res.checked_conditions


def test_duplicate_prose_type_promotes_to_done_when_goal_verified_complete() -> None:
    cfg = AppConfig()
    brain = MagicMock()
    brain.supports_vision.return_value = True
    prose = "Desktop automation performs repetitive UI tasks. It reads screen state to verify completion."
    brain.generate_cua_step.return_value = (
        "Type prose again.",
        ActionPlan(action=ActionType.TYPE, text=prose, reasoning="Type prose"),
    )
    pipe = DualMindPipeline(brain_manager=brain, memory=EpisodicMemory(), config=cfg)
    pipe.memory.record_step(
        action=ActionPlan(action=ActionType.TYPE, text=prose),
        screen_diff=0.05,
        success=True,
    )
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    with patch.object(
        pipe.goal_verifier,
        "verify_goal_state",
        return_value=GoalVerificationResult(verified=True, reason="ok"),
    ), patch.object(
        pipe.goal_verifier,
        "build_working_memory_snapshot",
        return_value="- Active Window: *Untitled - Notepad",
    ), patch.object(
        pipe.action_dispatcher,
        "dispatch",
        return_value=ActionResult(success=True, action_executed=ActionPlan(action=ActionType.DONE)),
    ) as mock_disp:
        rec = pipe.step(
            user_goal="Open Notepad and write a 2-sentence overview of desktop automation",
            screen_frame=frame,
            grounded_elements=[],
        )

    assert rec.action.action == ActionType.DONE
    assert mock_disp.call_args.kwargs["action"].action == ActionType.DONE


def test_unrequested_ctrl_s_promotes_to_done_when_goal_already_verified() -> None:
    cfg = AppConfig()
    brain = MagicMock()
    brain.supports_vision.return_value = True
    brain.generate_cua_step.return_value = (
        "Save work.",
        ActionPlan(action=ActionType.HOTKEY, keys=["ctrl", "s"], reasoning="Save document"),
    )
    pipe = DualMindPipeline(brain_manager=brain, memory=EpisodicMemory(), config=cfg)
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    with patch.object(
        pipe.goal_verifier,
        "verify_goal_state",
        return_value=GoalVerificationResult(verified=True, reason="Notepad verified"),
    ), patch.object(
        pipe.goal_verifier,
        "build_working_memory_snapshot",
        return_value="- Active Window: *Untitled - Notepad",
    ), patch.object(
        pipe.action_dispatcher,
        "dispatch",
        return_value=ActionResult(success=True, action_executed=ActionPlan(action=ActionType.DONE)),
    ) as mock_disp:
        rec = pipe.step(
            user_goal="Open Notepad and write a 2-sentence overview of desktop automation",
            screen_frame=frame,
            grounded_elements=[],
        )

    assert rec.action.action == ActionType.DONE
    assert mock_disp.call_args.kwargs["action"].action == ActionType.DONE


def test_repeat_unrequested_ctrl_s_blocked_when_goal_incomplete() -> None:
    cfg = AppConfig()
    brain = MagicMock()
    brain.supports_vision.return_value = True
    brain.generate_cua_step.return_value = (
        "Try Ctrl+S again.",
        ActionPlan(action=ActionType.HOTKEY, keys=["ctrl", "s"], reasoning="Save again"),
    )
    pipe = DualMindPipeline(brain_manager=brain, memory=EpisodicMemory(), config=cfg)
    pipe.memory.record_step(
        action=ActionPlan(action=ActionType.HOTKEY, keys=["ctrl", "s"]),
        screen_diff=0.19,
        success=True,
    )
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    with patch.object(
        pipe.goal_verifier,
        "verify_goal_state",
        return_value=GoalVerificationResult(
            verified=False,
            reason="Notepad contains echoed prompt instructions instead of composed prose.",
        ),
    ), patch.object(
        pipe.goal_verifier,
        "build_working_memory_snapshot",
        return_value="- Active Window: *Untitled - Notepad",
    ), patch.object(
        pipe.action_dispatcher,
        "dispatch",
        return_value=ActionResult(success=True, action_executed=ActionPlan(action=ActionType.WAIT)),
    ) as mock_disp:
        rec = pipe.step(
            user_goal="Open Notepad and write a 2-sentence overview of desktop automation",
            screen_frame=frame,
            grounded_elements=[],
        )

    assert rec.action.action == ActionType.WAIT
    assert mock_disp.call_args.kwargs["action"].action == ActionType.WAIT
    assert pipe._cua_loop_warning is not None
    assert "Do NOT press Ctrl+S" in pipe._cua_loop_warning
