"""
tests/test_launch_grounding_fix.py - Unit tests validating launch grounding, Run dialog redirection,
premature DONE interception, and process attribution fixes.
"""

from unittest.mock import MagicMock
import pytest

from parasite_ai.mind.dual_mind import DualMindPipeline
from parasite_ai.mind.memory import ActionPlan, ActionType, EpisodicMemory
from parasite_ai.mind.plan import LivingPlan, PlanStep, StepIntent, verify_step_completion
from parasite_ai.safety.window_guard import WindowInfo
from parasite_ai.ui.types import UIElement
from parasite_ai.vision.grounding import ScreenGrounder


def test_uielement_and_som_summary_process_attribution() -> None:
    """Validates that UIElement carries process_name and window_title and formats them in SOM summary."""
    grounder = ScreenGrounder()
    elem1 = UIElement.from_bbox(
        id=1,
        bbox=(26, 26, 993, 519),
        label="Text Area",
        role="Document",
        process_name="WindowsTerminal.exe",
        window_title="Developer PowerShell",
    )
    elem2 = UIElement.from_bbox(
        id=2,
        bbox=(230, 934, 297, 17),
        label="Open:",
        role="Edit",
        process_name="explorer.exe",
        window_title="Run",
    )

    summary = grounder.format_som_summary([elem1, elem2])
    assert 'app: WindowsTerminal.exe' in summary
    assert 'window: "Developer PowerShell"' in summary
    assert 'app: explorer.exe' in summary
    assert 'window: "Run"' in summary


def test_verify_step_completion_rejects_non_matching_active_window() -> None:
    """
    Validates that verify_step_completion for LAUNCH_OR_ACTIVATE rejects visual diff >= 0.02
    when current_window is known and does not match target_app (e.g. Run dialog open instead of Notepad).
    """
    step = PlanStep(
        step_id=1,
        intent=StepIntent.LAUNCH_OR_ACTIVATE,
        description="Launch or focus target application: notepad",
        target_description="notepad",
        success_criteria="Application 'notepad' is visible and active on desktop",
    )
    action = ActionPlan(action=ActionType.HOTKEY, keys=["win", "r"], reasoning="Open Windows Run dialog")
    from parasite_ai.mind.dual_mind import ActionResult
    result = ActionResult(success=True)

    # Active window is the Run dialog (explorer.exe), NOT notepad
    run_dialog_window = WindowInfo(
        hwnd=1234,
        title="Run",
        class_name="#32770",
        process_name="explorer.exe",
        process_path="C:\\Windows\\explorer.exe",
        pid=999,
        rect=(100, 800, 500, 1000),
        is_sensitive=False,
        reason="",
    )

    # Even with high screen diff (e.g. 0.22), it must NOT declare launch complete
    assert verify_step_completion(step, action, result, screen_diff=0.22, current_window=run_dialog_window) is False

    # Once Notepad becomes the active window, it must verify successfully
    notepad_window = WindowInfo(
        hwnd=5678,
        title="Untitled - Notepad",
        class_name="Notepad",
        process_name="notepad.exe",
        process_path="C:\\Windows\\notepad.exe",
        pid=1000,
        rect=(50, 50, 800, 600),
        is_sensitive=False,
        reason="",
    )
    assert verify_step_completion(step, action, result, screen_diff=0.0, current_window=notepad_window) is True


def test_dual_mind_redirects_run_dialog_launch() -> None:
    """
    Validates that when the Run dialog is open and target app is not active,
    misdirected clicks targeting background windows are redirected to type target app into the Run dialog.
    """
    mock_brain = MagicMock()
    mock_brain.generate_thought.return_value = "I see the Run dialog and a text area."
    # Brain attempts to click the background text area (Target 1) instead of the Run edit box (Target 2)
    mock_brain.generate_action.return_value = {
        "action": "CLICK",
        "target_id": 1,
        "reasoning": "Clicking background text area mistakenly",
    }

    elements = [
        UIElement.from_bbox(
            id=1,
            bbox=(26, 26, 993, 519),
            label="Text Area",
            role="Document",
            process_name="WindowsTerminal.exe",
            window_title="Developer PowerShell",
        ),
        UIElement.from_bbox(
            id=2,
            bbox=(230, 934, 297, 17),
            label="Open:",
            role="Edit",
            process_name="explorer.exe",
            window_title="Run",
        ),
    ]

    pipeline = DualMindPipeline(brain_manager=mock_brain)
    mock_guard = MagicMock()
    mock_guard.get_active_window.return_value = WindowInfo(
        hwnd=1234,
        title="Run",
        class_name="#32770",
        process_name="explorer.exe",
        process_path="",
        pid=999,
        rect=(0, 0, 400, 300),
        is_sensitive=False,
        reason="",
    )
    pipeline.window_guard = mock_guard

    rec = pipeline.step(
        user_goal="open notepad and write an introduction",
        grounded_elements=elements,
    )

    # Must be redirected to CLICK_AND_TYPE into Target 2 with "notepad" and submit=True
    assert rec.action.action == ActionType.CLICK_AND_TYPE
    assert rec.action.target_id == 2
    assert "notepad" in (rec.action.text or "").lower()
    assert rec.action.submit is True


def test_dual_mind_intercepts_premature_done() -> None:
    """
    Validates that if the brain emits DONE before the target application is active,
    DualMind intercepts premature DONE and resolves application launch.
    """
    mock_brain = MagicMock()
    mock_brain.generate_thought.return_value = "I think the goal is finished."
    mock_brain.generate_action.return_value = {
        "action": "DONE",
        "reasoning": "Task completed prematurely",
    }

    elements = [
        UIElement.from_bbox(
            id=1,
            bbox=(26, 26, 993, 519),
            label="Text Area",
            role="Document",
            process_name="WindowsTerminal.exe",
            window_title="Developer PowerShell",
        ),
    ]

    pipeline = DualMindPipeline(brain_manager=mock_brain)
    mock_guard = MagicMock()
    mock_guard.get_active_window.return_value = WindowInfo(
        hwnd=1234,
        title="Developer PowerShell",
        class_name="ConsoleWindowClass",
        process_name="WindowsTerminal.exe",
        process_path="",
        pid=999,
        rect=(0, 0, 400, 300),
        is_sensitive=False,
        reason="",
    )
    pipeline.window_guard = mock_guard

    rec = pipeline.step(
        user_goal="open notepad and write an introduction",
        grounded_elements=elements,
    )

    # Must NOT execute DONE; must initiate launch (e.g. Win key or Win+R hotkey)
    assert rec.action.action != ActionType.DONE
    assert rec.action.action in (ActionType.HOTKEY, ActionType.CLICK, ActionType.CLICK_AND_TYPE)
