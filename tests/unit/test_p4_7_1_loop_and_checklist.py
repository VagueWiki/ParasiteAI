"""Targeted unit tests for Stint P4.7.1 (0.4.7.1) unrequested-save suppression, checklist coverage, and loop warnings."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from parasite_ai.config import AppConfig
from parasite_ai.mind.dual_mind import ActionResult, DualMindPipeline
from parasite_ai.mind.memory import ActionPlan, ActionType, CadenceTier, EpisodicMemory
from parasite_ai.mind.uitars_parser import UITARS_SYSTEM_PROMPT, parse_uitars_action
from parasite_ai.mind.verifier import RuntimeGoalVerifier

pytestmark = pytest.mark.unit


def test_uitars_system_prompt_prohibits_unrequested_saves_and_encourages_completion() -> None:
    assert "COMPLETION & NO UNREQUESTED SAVES" in UITARS_SYSTEM_PROMPT
    assert "GENERATIVE WRITING TASKS" in UITARS_SYSTEM_PROMPT
    assert "unless the user task explicitly asks you to save, export, or close" in UITARS_SYSTEM_PROMPT
    assert "emit finished() immediately" in UITARS_SYSTEM_PROMPT


def test_uitars_parser_newline_suffix_does_not_truncate_trailing_n() -> None:
    """Regression: rstrip('\\n') must never strip trailing 'n' from words like automation/python/open."""
    for word in ("A 2-sentence overview of desktop automation", "python", "open"):
        _, act = parse_uitars_action(f"Thought: type.\nAction: type(content='{word}\\n')")
        assert act.action == ActionType.TYPE
        assert act.text == word
        assert act.submit is True

    _, multiline = parse_uitars_action("Thought: type.\nAction: type(content='line1\\nline2\\n\\n')")
    assert multiline.text == "line1\\nline2"
    assert multiline.submit is True


def test_single_char_type_does_not_ping_pong_to_enter() -> None:
    cfg = AppConfig()
    brain = MagicMock()
    brain.supports_vision.return_value = True
    brain.generate_cua_step.return_value = (
        "Add trailing letter.",
        ActionPlan(action=ActionType.TYPE, text="n", reasoning="Type n"),
    )
    pipe = DualMindPipeline(brain_manager=brain, memory=EpisodicMemory(), config=cfg)
    pipe.memory.record_step(
        action=ActionPlan(action=ActionType.TYPE, text="n"),
        screen_diff=0.05,
        success=True,
    )
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    with patch.object(
        pipe.action_dispatcher,
        "dispatch",
        return_value=ActionResult(success=True, action_executed=ActionPlan(action=ActionType.TYPE, text="n")),
    ):
        rec = pipe.step(user_goal="Write overview", screen_frame=frame, grounded_elements=[])
    assert rec.action.action == ActionType.TYPE
    assert rec.action.text == "n"


def test_goal_verifier_rejects_2_sentence_echo_and_accepts_prose() -> None:
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
        res_echo = verifier.verify_goal_state(goal)
        assert res_echo.verified is False

    prose = "Desktop automation executes UI workflows visibly. It verifies outcomes before finishing."
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=windows), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value=prose):
        res_ok = verifier.verify_goal_state(goal)
        assert res_ok.verified is True


def test_goal_verifier_checklist_covers_unquoted_notepad_composition_and_all_checked_hint() -> None:
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
    sample_prose = "Desktop automation coordinates OS inputs safely. It verifies results before concluding."

    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=windows), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value=sample_prose):
        snap = verifier.build_working_memory_snapshot(
            user_goal="Open Notepad and write a 2-sentence overview of desktop automation",
        )
        assert "[x] Launch Notepad" in snap
        assert "[x] Compose text in Notepad" in snap
        assert "All derived sub-goals are satisfied [x]" in snap
        assert "emit finished() immediately" in snap

    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=windows), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value=""):
        snap_empty = verifier.build_working_memory_snapshot(
            user_goal="Open Notepad and write a 2-sentence overview of desktop automation",
        )
        assert "[x] Launch Notepad" in snap_empty
        assert "[ ] Compose text in Notepad" in snap_empty
        assert "All derived sub-goals are satisfied [x]" not in snap_empty


def test_episodic_memory_distinguishes_oscillation_strikes_from_zero_diff_without_ctrl_s() -> None:
    mem = EpisodicMemory()
    mem.record_step(
        action=ActionPlan(action=ActionType.HOTKEY, keys=["ctrl", "s"], reasoning="save"),
        success=False,
        screen_diff=0.19,
        error_message="Action oscillation loop detected",
    )
    prompt_osc = mem.format_for_prompt()
    assert "LOOP STRIKE" in prompt_osc
    assert "NO SCREEN CHANGE" not in prompt_osc
    assert "Ctrl+S" not in prompt_osc

    mem2 = EpisodicMemory()
    mem2.record_step(
        action=ActionPlan(action=ActionType.CLICK, coordinates=(100, 100), reasoning="click"),
        success=True,
        screen_diff=0.0,
    )
    prompt_nodiff = mem2.format_for_prompt()
    assert "NO SCREEN CHANGE" in prompt_nodiff
    assert "Ctrl+S" not in prompt_nodiff


def test_dual_mind_tier2_suppressed_injects_cua_loop_warning_into_working_memory() -> None:
    cfg = AppConfig()
    brain = MagicMock()
    brain.supports_vision.return_value = True
    brain.generate_cua_step.return_value = (
        "Already done.",
        ActionPlan(action=ActionType.DONE, reasoning="Goal complete"),
    )

    pipe = DualMindPipeline(
        brain_manager=brain,
        memory=EpisodicMemory(),
        config=cfg,
    )
    pipe.goal_verifier = MagicMock()
    pipe.goal_verifier.build_working_memory_snapshot.return_value = "- Active Window: Notepad"
    pipe.goal_verifier.verify_goal_state.return_value = MagicMock(verified=True, reason="ok")

    pipe.escalation_sm.current_tier = CadenceTier.TIER_2_CONSULT
    pipe.escalation_sm.local_strikes = 3

    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    pipe.step(
        user_goal="Open Notepad and write a 2-sentence overview of desktop automation",
        screen_frame=frame,
        grounded_elements=[],
    )

    brain.generate_cua_step.assert_called_once()
    wm_passed = brain.generate_cua_step.call_args.kwargs["working_memory_context"]
    assert "Loop Intervention Warning:" in wm_passed
    assert "alternating cycle detected" in wm_passed


def test_goal_verifier_prioritizes_non_echo_over_missing_punctuation() -> None:
    """P4.7.4 regression: unpunctuated echoed prompt must return notepad_greeting_non_echo, not too-short."""
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
         patch(
             "parasite_ai.mind.verifier.read_notepad_buffer",
             return_value="A 2-sentence overview of desktop automation\r\n\r\n",
         ):
        res = verifier.verify_goal_state(goal)
        assert res.verified is False
        assert res.checked_conditions == ["notepad_greeting_non_echo"]
        assert "echoed prompt instructions" in res.reason
        assert "ctrl a" in res.reason


def test_dual_mind_notepad_composition_veto_suppresses_save_as_commit_hint() -> None:
    """P4.7.4 regression: consecutive >= 2 Notepad composition vetoes must warn against Ctrl+S, not suggest Save As."""
    cfg = AppConfig()
    brain = MagicMock()
    brain.supports_vision.return_value = True
    brain.generate_cua_step.return_value = (
        "Done.",
        ActionPlan(action=ActionType.DONE, reasoning="Goal complete"),
    )

    pipe = DualMindPipeline(
        brain_manager=brain,
        memory=EpisodicMemory(),
        config=cfg,
    )
    pipe.goal_verifier = MagicMock()
    pipe.goal_verifier.build_working_memory_snapshot.return_value = "- Active Window: Notepad"
    pipe.goal_verifier.verify_goal_state.return_value = MagicMock(
        verified=False,
        reason="Notepad contains echoed prompt instructions instead of composed prose.",
        checked_conditions=["notepad_greeting_non_echo"],
    )

    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    with patch.object(
        pipe.action_dispatcher,
        "dispatch",
        return_value=ActionResult(success=False, action_executed=ActionPlan(action=ActionType.WAIT)),
    ):
        pipe.step(
            user_goal="Open Notepad and write a 2-sentence overview of desktop automation",
            screen_frame=frame,
            grounded_elements=[],
        )
        rec = pipe.step(
            user_goal="Open Notepad and write a 2-sentence overview of desktop automation",
            screen_frame=frame,
            grounded_elements=[],
        )

    assert rec.error_message is not None
    assert "Do NOT press Ctrl+S" in rec.error_message
    assert "Save As box" not in rec.error_message


def test_goal_verifier_rejects_single_sentence_topic_echo_and_accepts_two_sentences() -> None:
    """P4.7.7 regression: 1-sentence topic echo ('A brief overview of desktop automation.') must fail."""
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

    # Case 1: 1-sentence goal-phrase echo -> rejected by both verify_goal_state and checklist
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=windows), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value="A brief overview of desktop automation."):
        res_echo = verifier.verify_goal_state(goal)
        assert res_echo.verified is False
        assert res_echo.checked_conditions in (["notepad_greeting_non_echo"], ["notepad_sentence_count"])
        checklist = verifier._derive_subgoal_checklist(goal, windows)
        assert any(item.startswith("[ ] Compose text in Notepad") for item in checklist)

    # Case 2: 1 original sentence (not echo) when 2 sentences requested -> rejected on sentence count
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=windows), \
         patch(
             "parasite_ai.mind.verifier.read_notepad_buffer",
             return_value="Software tools automate repetitive tasks reliably on personal computers.",
         ):
        res_one = verifier.verify_goal_state(goal)
        assert res_one.verified is False
        assert res_one.checked_conditions == ["notepad_sentence_count"]
        assert "1 complete sentence" in res_one.reason

    # Case 3: 2 genuine original sentences -> accepted
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=windows), \
         patch(
             "parasite_ai.mind.verifier.read_notepad_buffer",
             return_value=(
                 "Software tools automate repetitive UI tasks reliably on personal computers. "
                 "They save time and reduce manual errors across everyday workflows."
             ),
         ):
        res_ok = verifier.verify_goal_state(goal)
        assert res_ok.verified is True


def test_goal_verifier_rejects_unexpected_notepad_save_modal_dialog() -> None:
    """P4.7.7 regression: open #32770 'Notepad' Save-Changes dialog must block DONE on non-close goals."""
    verifier = RuntimeGoalVerifier()
    windows = [
        {
            "hwnd": 200,
            "title": "Notepad",
            "class_name": "#32770",
            "pid": 4321,
            "process_name": "notepad.exe",
            "is_minimized": False,
            "rect": (700, 400, 1100, 600),
        },
        {
            "hwnd": 100,
            "title": "*Untitled - Notepad",
            "class_name": "Notepad",
            "pid": 4321,
            "process_name": "notepad.exe",
            "is_minimized": False,
            "rect": (50, 50, 850, 650),
        },
    ]
    goal = "Open Notepad and write a 2-sentence overview of desktop automation"
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=windows), \
         patch(
             "parasite_ai.mind.verifier.read_notepad_buffer",
             return_value=(
                 "Software tools automate repetitive UI tasks reliably on personal computers. "
                 "They save time and reduce manual errors across everyday workflows."
             ),
         ):
        res = verifier.verify_goal_state(goal)
        assert res.verified is False
        assert res.checked_conditions == ["unexpected_modal_dialog"]
        checklist = verifier._derive_subgoal_checklist(goal, windows)
        assert any("Dismiss unexpected dialog ('Notepad')" in item for item in checklist)
