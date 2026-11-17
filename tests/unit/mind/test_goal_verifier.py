"""
tests/unit/mind/test_goal_verifier.py - Unit Tests for Runtime Pre-DONE Verifier & Feedback.

Tests domain-agnostic post-condition checks: window launch/close/minimize,
Notepad buffer text and composition, file creation/rename/append, clipboard
verification, modal dialog dismissal, and DualMindPipeline pre-DONE veto interception.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from parasite_ai.mind.dual_mind import DualMindPipeline
from parasite_ai.mind.memory import ActionPlan, ActionType, EpisodicMemory
from parasite_ai.mind.verifier import GoalVerificationResult, RuntimeGoalVerifier


# ---------------------------------------------------------------------------
# 1. Window Launch, Close, and Minimization Checks
# ---------------------------------------------------------------------------

def test_verifier_window_launch_accepts_when_open() -> None:
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {"process_name": "notepad.exe", "title": "Untitled - Notepad", "class_name": "Notepad", "is_minimized": False}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows):
        res = verifier.verify_goal_state("Open Notepad")
        assert res.verified is True
        assert "verified" in res.reason.lower()


def test_verifier_window_launch_rejects_when_missing() -> None:
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {"process_name": "explorer.exe", "title": "Desktop", "class_name": "Progman", "is_minimized": False}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows):
        res = verifier.verify_goal_state("Open Notepad")
        assert res.verified is False
        assert "Notepad window is not open" in res.reason


def test_verifier_window_close_accepts_when_closed() -> None:
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {"process_name": "explorer.exe", "title": "Desktop", "class_name": "Progman", "is_minimized": False}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows):
        res = verifier.verify_goal_state("Close Notepad")
        assert res.verified is True
        assert "successfully closed" in res.reason


def test_verifier_window_close_rejects_when_still_open() -> None:
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {"process_name": "notepad.exe", "title": "Untitled - Notepad", "class_name": "Notepad", "is_minimized": False}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows):
        res = verifier.verify_goal_state("Close Notepad")
        assert res.verified is False
        assert "is still open" in res.reason


def test_verifier_window_minimize_accepts_when_iconic() -> None:
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {"process_name": "notepad.exe", "title": "Untitled - Notepad", "class_name": "Notepad", "is_minimized": True}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows):
        res = verifier.verify_goal_state("Minimize Notepad")
        assert res.verified is True
        assert "verified minimized" in res.reason


def test_verifier_window_minimize_rejects_when_not_iconic() -> None:
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {"process_name": "notepad.exe", "title": "Untitled - Notepad", "class_name": "Notepad", "is_minimized": False}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows):
        res = verifier.verify_goal_state("Minimize Notepad")
        assert res.verified is False
        assert "is not minimized" in res.reason


# ---------------------------------------------------------------------------
# 2. Notepad Text Content & Prose Composition Checks
# ---------------------------------------------------------------------------

def test_verifier_notepad_typing_accepts_matching_text() -> None:
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {"process_name": "notepad.exe", "title": "Untitled - Notepad", "class_name": "Notepad", "is_minimized": False}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value="Benchmark Alpha Test 42"):
        res = verifier.verify_goal_state("Open Notepad and type 'Benchmark Alpha Test 42'")
        assert res.verified is True


def test_verifier_notepad_typing_rejects_missing_text() -> None:
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {"process_name": "notepad.exe", "title": "Untitled - Notepad", "class_name": "Notepad", "is_minimized": False}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value=""):
        res = verifier.verify_goal_state("Open Notepad and type 'Benchmark Alpha Test 42'")
        assert res.verified is False
        assert "empty" in res.reason.lower()


def test_verifier_notepad_composition_rejects_echoed_prompt() -> None:
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {"process_name": "notepad.exe", "title": "Untitled - Notepad", "class_name": "Notepad", "is_minimized": False}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value="Open Notepad and write a short two-sentence greeting."):
        res = verifier.verify_goal_state("Open Notepad and write a short two-sentence greeting")
        assert res.verified is False
        assert "echoed" in res.reason.lower()


def test_verifier_notepad_composition_accepts_genuine_prose() -> None:
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {"process_name": "notepad.exe", "title": "Untitled - Notepad", "class_name": "Notepad", "is_minimized": False}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value="Hello there! Welcome to the desktop automated test suite."):
        res = verifier.verify_goal_state("Open Notepad and write a short two-sentence greeting")
        assert res.verified is True


# ---------------------------------------------------------------------------
# 3. File Operations: Save, Append, Rename & Directory Creation
# ---------------------------------------------------------------------------

def test_verifier_file_save_accepts_when_file_exists(tmp_path: Path) -> None:
    verifier = RuntimeGoalVerifier()
    test_file = tmp_path / "note.txt"
    test_file.write_text("Saved Note 101", encoding="utf-8")

    goal = f"Open Notepad, type 'Saved Note 101', and save it as {test_file}"
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=[]):
        res = verifier.verify_goal_state(goal)
        assert res.verified is True


def test_verifier_file_save_rejects_when_file_missing(tmp_path: Path) -> None:
    verifier = RuntimeGoalVerifier()
    test_file = tmp_path / "nonexistent.txt"
    goal = f"Open Notepad, type 'Saved Note 101', and save it as {test_file}"
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=[]):
        res = verifier.verify_goal_state(goal)
        assert res.verified is False
        assert "has not been saved to disk" in res.reason


def test_verifier_file_rename_verified(tmp_path: Path) -> None:
    verifier = RuntimeGoalVerifier()
    old_file = tmp_path / "old.txt"
    new_file = tmp_path / "new.txt"
    new_file.write_text("content", encoding="utf-8")

    goal = f"Open File Explorer to {tmp_path} and rename old.txt to new.txt"
    res = verifier.verify_goal_state(goal)
    assert res.verified is True


def test_verifier_directory_creation_verified(tmp_path: Path) -> None:
    verifier = RuntimeGoalVerifier()
    new_dir = tmp_path / "Reports"
    new_dir.mkdir(parents=True, exist_ok=True)

    goal = f"Create a new folder named 'Reports' inside {tmp_path} in File Explorer"
    res = verifier.verify_goal_state(goal)
    assert res.verified is True


# ---------------------------------------------------------------------------
# 4. Clipboard and Modal Dialog Checks
# ---------------------------------------------------------------------------

def test_verifier_clipboard_verified() -> None:
    verifier = RuntimeGoalVerifier()
    with patch("pyperclip.paste", return_value="Draft"):
        res = verifier.verify_goal_state("Open Notepad, type 'Draft', select all text, and copy it to the clipboard")
        assert res.verified is True


def test_verifier_modal_dialog_dismissal_rejects_when_dialog_still_open() -> None:
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {"process_name": "python.exe", "title": "Benchmark System Error", "class_name": "#32770", "is_minimized": False}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows):
        res = verifier.verify_goal_state("Close the error dialog and then open Notepad")
        assert res.verified is False
        assert "still open" in res.reason


# ---------------------------------------------------------------------------
# 5. DualMindPipeline Pre-DONE Interception Integration
# ---------------------------------------------------------------------------

def test_dual_mind_vetoes_premature_done_and_injects_reason() -> None:
    mock_brain = MagicMock()
    mock_brain.supports_vision.return_value = True
    # Model prematurely emits DONE on Step 1
    mock_brain.generate_cua_step.return_value = ("Finished task", ActionPlan(action=ActionType.DONE, reasoning="Done"))

    mem = EpisodicMemory()
    pipeline = DualMindPipeline(
        brain_manager=mock_brain,
        memory=mem,
        config=None,
    )

    # Mock verifier to report missing window
    pipeline.goal_verifier.verify_goal_state = MagicMock(
        return_value=GoalVerificationResult(
            verified=False,
            reason="Notepad window is not open. Launch Notepad before finishing.",
            checked_conditions=["notepad_open"],
        )
    )

    rec = pipeline.step(user_goal="Open Notepad")

    # DONE was converted to WAIT(success=False)
    assert rec.action.action == ActionType.WAIT
    assert rec.success is False
    assert "Premature DONE rejected" in (rec.error_message or "")
    assert "Notepad window is not open" in (rec.error_message or "")

    # Next prompt format includes the diagnostic reason tag
    prompt_context = mem.format_for_prompt()
    assert "Premature DONE rejected: Notepad window is not open" in prompt_context


# ---------------------------------------------------------------------------
# 6. Working Memory Snapshot & Sub-Goal Checklist Tests (Stint P2.6.3)
# ---------------------------------------------------------------------------

def test_build_working_memory_snapshot_multi_app_checklist() -> None:
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {"process_name": "CalculatorApp.exe", "title": "Calculator", "class_name": "ApplicationFrameWindow", "is_minimized": False, "pid": 1111},
        {"process_name": "notepad.exe", "title": "Untitled - Notepad", "class_name": "Notepad", "is_minimized": False, "pid": 2222},
    ]
    goal = "Open Calculator, compute 144 / 12, then open Notepad and type the result"

    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value="12"):
        snapshot = verifier.build_working_memory_snapshot(user_goal=goal)

    assert "- Open Windows:" in snapshot
    assert "Calculator (CalculatorApp.exe)" in snapshot
    assert "Untitled - Notepad (notepad.exe)" in snapshot
    assert '- Notepad Buffer: "12"' in snapshot
    assert "- Sub-Goal Progress:" in snapshot
    assert "[x] Launch Calculator" in snapshot
    assert "[x] Launch Notepad" in snapshot
    assert "[x] Type result '12' into Notepad" in snapshot


def test_build_working_memory_snapshot_file_save_and_modal_dialog(tmp_path: Path) -> None:
    verifier = RuntimeGoalVerifier()
    test_file = tmp_path / "memo.txt"
    goal = f"Open Notepad, type 'Important', and save it as {test_file}"

    # State A: File not saved, Save As dialog still open
    mock_windows_a = [
        {"process_name": "notepad.exe", "title": "Save As", "class_name": "#32770", "is_minimized": False, "pid": 3333},
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows_a), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value="Important"):
        snapshot_a = verifier.build_working_memory_snapshot(user_goal=goal)

    assert "⚠️ Blocking Modal Dialog: Save As (Interact with dialog first)" in snapshot_a
    assert f"[ ] Save file '{test_file.name}' to disk" in snapshot_a

    # State B: File written to disk, Save As dialog closed
    test_file.write_text("Important", encoding="utf-8")
    mock_windows_b = [
        {"process_name": "notepad.exe", "title": "memo.txt - Notepad", "class_name": "Notepad", "is_minimized": False, "pid": 3333},
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows_b), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value="Important"):
        snapshot_b = verifier.build_working_memory_snapshot(user_goal=goal)

    assert "⚠️ Blocking Modal Dialog" not in snapshot_b
    assert f"[x] Save file '{test_file.name}' to disk" in snapshot_b


def test_build_working_memory_snapshot_window_geometry_and_taskbar() -> None:
    """Verifies that active window physical bounds and taskbar strip are injected in screen pixels without hardcoded heuristics."""
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {
            "process_name": "notepad.exe",
            "title": "Untitled - Notepad",
            "class_name": "Notepad",
            "is_minimized": False,
            "pid": 5555,
            "rect": (200, 150, 1000, 750),
        },
    ]

    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows):
        snapshot = verifier.build_working_memory_snapshot(user_goal="Close Notepad")

    assert "- Active Window: Untitled - Notepad (notepad.exe) [Bounds: x=200, y=150, w=800, h=600]" in snapshot
    assert "Close Button ('X')" not in snapshot
    assert "- Desktop Taskbar: Bottom strip (y=1040..1080)" in snapshot
    assert "Start button at" not in snapshot


# ---------------------------------------------------------------------------
# 7. Stint P3.2: Compound Working Memory Checklists & Taskbar Affordances
# ---------------------------------------------------------------------------

def test_build_working_memory_snapshot_background_apps_affordance_minimized() -> None:
    """Verifies that minimized target applications are identified with taskbar restore guidance."""
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {
            "process_name": "CalculatorApp.exe",
            "title": "Calculator",
            "class_name": "ApplicationFrameWindow",
            "is_minimized": False,
            "pid": 1001,
            "rect": (100, 100, 600, 700),
        },
        {
            "process_name": "notepad.exe",
            "title": "Untitled - Notepad",
            "class_name": "Notepad",
            "is_minimized": True,
            "pid": 1002,
            "rect": (0, 0, 0, 0),
        },
    ]

    goal = "Open Calculator, compute 144 / 12, and type the result into the open Notepad window"
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows):
        snapshot = verifier.build_working_memory_snapshot(user_goal=goal)

    assert "- Running Background Applications: Untitled - Notepad (notepad.exe) [Minimized] -> Click taskbar at y=1040..1080 to restore" in snapshot


def test_build_working_memory_snapshot_background_apps_affordance_behind_active() -> None:
    """Verifies that unminimized non-foreground target applications are surfaced as In Background."""
    verifier = RuntimeGoalVerifier()
    mock_windows = [
        {
            "process_name": "CalculatorApp.exe",
            "title": "Calculator",
            "class_name": "ApplicationFrameWindow",
            "is_minimized": False,
            "pid": 2001,
            "rect": (100, 100, 600, 700),
        },
        {
            "process_name": "notepad.exe",
            "title": "Untitled - Notepad",
            "class_name": "Notepad",
            "is_minimized": False,
            "pid": 2002,
            "rect": (200, 200, 800, 800),
        },
    ]

    goal = "Open Calculator, compute 144 / 12, and type the result into the open Notepad window"
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=mock_windows):
        snapshot = verifier.build_working_memory_snapshot(user_goal=goal)

    assert "- Running Background Applications: Untitled - Notepad (notepad.exe) [In Background] -> Click taskbar at y=1040..1080 to restore" in snapshot


def test_subgoal_checklist_calculator_to_notepad_sequence(tmp_path: Path) -> None:
    """Verifies chronological phased checklist generation for Calculator -> Notepad file workflows."""
    verifier = RuntimeGoalVerifier()
    target_file = tmp_path / "total.txt"
    goal = f"Compute 25 * 4 in Calculator, write 'Total: 100' in Notepad, and save to {target_file}"

    # Stage 0: Neither app open
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=[]), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value=""):
        items_0 = verifier._derive_subgoal_checklist(goal, [])
    assert items_0 == [
        "[ ] Launch Calculator",
        "[ ] Compute 25 * 4 in Calculator",
        "[ ] Launch Notepad",
        "[ ] Type 'Total: 100' into Notepad",
        f"[ ] Save file '{target_file.name}' to disk",
    ]

    # Stage 1: Calculator launched
    calc_win = [{"process_name": "CalculatorApp.exe", "title": "Calculator", "class_name": "ApplicationFrameWindow", "is_minimized": False, "pid": 3001}]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=calc_win), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value=""):
        items_1 = verifier._derive_subgoal_checklist(goal, calc_win)
    assert items_1[0] == "[x] Launch Calculator"
    assert items_1[1] == "[ ] Compute 25 * 4 in Calculator"

    # Stage 2: Notepad launched, text typed
    both_wins = [
        {"process_name": "CalculatorApp.exe", "title": "Calculator", "class_name": "ApplicationFrameWindow", "is_minimized": False, "pid": 3001},
        {"process_name": "notepad.exe", "title": "Untitled - Notepad", "class_name": "Notepad", "is_minimized": False, "pid": 3002},
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=both_wins), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value="Total: 100"):
        items_2 = verifier._derive_subgoal_checklist(goal, both_wins)
    assert items_2[0] == "[x] Launch Calculator"
    assert items_2[1] == "[x] Compute 25 * 4 in Calculator"
    assert items_2[2] == "[x] Launch Notepad"
    assert items_2[3] == "[x] Type 'Total: 100' into Notepad"
    assert items_2[4] == f"[ ] Save file '{target_file.name}' to disk"

    # Stage 3: File saved to disk
    target_file.write_text("Total: 100", encoding="utf-8")
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=both_wins), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value="Total: 100"):
        items_3 = verifier._derive_subgoal_checklist(goal, both_wins)
    assert items_3[4] == f"[x] Save file '{target_file.name}' to disk"


def test_subgoal_checklist_browser_to_notepad_sequence() -> None:
    """Verifies chronological phased checklist generation for Browser -> Notepad cross-app tasks."""
    verifier = RuntimeGoalVerifier()
    goal = "Open Chrome, go to https://example.com, and write the main heading text into Notepad"

    # Stage 0: Clean state
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=[]), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value=""):
        items_0 = verifier._derive_subgoal_checklist(goal, [])
    assert items_0 == [
        "[ ] Launch Browser",
        "[ ] Navigate to https://example.com",
        "[ ] Launch Notepad",
        "[ ] Record heading text into Notepad",
    ]

    # Stage 1: Chrome navigated to example.com and Notepad open with heading recorded
    active_wins = [
        {"process_name": "chrome.exe", "title": "Example Domain - Google Chrome", "class_name": "Chrome_WidgetWin_1", "is_minimized": False, "pid": 4001},
        {"process_name": "notepad.exe", "title": "Untitled - Notepad", "class_name": "Notepad", "is_minimized": False, "pid": 4002},
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=active_wins), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value="Example Domain"):
        items_1 = verifier._derive_subgoal_checklist(goal, active_wins)
    assert items_1 == [
        "[x] Launch Browser",
        "[x] Navigate to https://example.com",
        "[x] Launch Notepad",
        "[x] Record heading text into Notepad",
    ]


def test_subgoal_checklist_seed_file_and_token_harvest(tmp_path: Path) -> None:
    """Verifies checklist generation for seed file appending and clipboard token harvesting."""
    verifier = RuntimeGoalVerifier()
    seed_file = tmp_path / "seed.txt"
    goal_seed = f"Open {seed_file} in Notepad and append ' - Approved' to the end"

    # Seed file open in Notepad with append text
    notepad_seed = [
        {"process_name": "notepad.exe", "title": f"{seed_file.name} - Notepad", "class_name": "Notepad", "is_minimized": False, "pid": 5001}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=notepad_seed), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value="Project Proposal v1 - Approved"):
        items_seed = verifier._derive_subgoal_checklist(goal_seed, notepad_seed)
    assert items_seed == [
        f"[x] Open {seed_file.name} in Notepad",
        "[x] Append ' - Approved' to Notepad",
    ]

    # Token harvesting to clipboard
    goal_harvest = "Copy the token text from the open Notepad window to the clipboard"
    with patch("pyperclip.paste", return_value="TOKEN_9941"):
        items_harvest = verifier._derive_subgoal_checklist(goal_harvest, notepad_seed)
    assert items_harvest == [
        "[x] Copy token to clipboard",
    ]


# ---------------------------------------------------------------------------
# 6. Teardown Working Memory Affordances & Verification (Stint P3.3.2)
# ---------------------------------------------------------------------------

def test_working_memory_injects_closed_process_affordance_for_teardown_goals() -> None:
    """Verifies that teardown goals inject explicit CLOSED affordances once target is terminated."""
    verifier = RuntimeGoalVerifier()
    goal = "Close the open Notepad window and choose Don't Save on the prompt"

    # Stage 1: Notepad is still open with dirty draft
    open_wins = [
        {"process_name": "notepad.exe", "title": "Untitled - Notepad", "class_name": "Notepad", "is_minimized": False, "pid": 6001}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=open_wins), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value="Draft"):
        snap_open = verifier.build_working_memory_snapshot(goal)
        res_open = verifier.verify_goal_state(goal)

    assert "Target Application Status: notepad is CLOSED" not in snap_open
    assert "[ ] Close notepad" in snap_open
    assert "[ ] Choose 'Don't Save'" in snap_open
    assert res_open.verified is False
    assert any(term in res_open.reason.lower() for term in ("still open", "still running"))

    # Stage 2: Notepad has closed and terminated
    closed_wins = [
        {"process_name": "explorer.exe", "title": "Desktop", "class_name": "Progman", "is_minimized": False, "pid": 1000}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=closed_wins), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value=""):
        snap_closed = verifier.build_working_memory_snapshot(goal)
        res_closed = verifier.verify_goal_state(goal)

    assert "- Target Application Status: notepad is CLOSED / TERMINATED (0 open windows). Teardown goal is fulfilled -> Emit DONE." in snap_closed
    assert "[x] Close notepad" in snap_closed
    assert "[x] Discard unsaved changes ('Don't Save')" in snap_closed
    assert res_closed.verified is True
    assert any(term in res_closed.reason.lower() for term in ("successfully closed", "notepad closed", "dialog dismissed"))


def test_working_memory_does_not_inject_closed_affordance_for_launch_goals() -> None:
    """Verifies that launch goals do NOT inject closed affordance when target app is not yet open."""
    verifier = RuntimeGoalVerifier()
    goal = "Open Notepad"

    closed_wins = [
        {"process_name": "explorer.exe", "title": "Desktop", "class_name": "Progman", "is_minimized": False, "pid": 1000}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=closed_wins), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value=""):
        snap = verifier.build_working_memory_snapshot(goal)
        res = verifier.verify_goal_state(goal)

    assert "Target Application Status: notepad is CLOSED" not in snap
    assert "[ ] Launch Notepad" in snap
    assert res.verified is False


def test_composite_modal_dismissal_and_app_launch_preserves_launch_prerequisite() -> None:
    """Verifies that composite goals (dismiss dialog + launch app) do not treat the launch target as teardown."""
    verifier = RuntimeGoalVerifier()
    goal = "Close the error dialog and then open Notepad"

    # Dialog dismissed, Notepad not open yet
    no_dialog_no_notepad = [
        {"process_name": "explorer.exe", "title": "Desktop", "class_name": "Progman", "is_minimized": False, "pid": 1000}
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=no_dialog_no_notepad), \
         patch("parasite_ai.mind.verifier.read_notepad_buffer", return_value=""):
        snap = verifier.build_working_memory_snapshot(goal)
        res = verifier.verify_goal_state(goal)

    assert "Target Application Status: notepad is CLOSED" not in snap
    assert "[x] Dismiss modal dialog" in snap
    assert "[ ] Launch Notepad" in snap
    assert res.verified is False
    assert "Notepad window is not open" in res.reason


def test_suite_yaml_task_timeouts_scale_proportionately() -> None:
    """Verifies all tasks in benchmarks/suite.yaml enforce timeout_sec >= max_steps * 8."""
    import yaml
    suite_file = Path("benchmarks/suite.yaml")
    assert suite_file.exists(), "suite.yaml must exist"
    data = yaml.safe_load(suite_file.read_text(encoding="utf-8"))
    tasks = data.get("tasks", []) + data.get("stretch_tasks", [])
    for task in tasks:
        tid = task["id"]
        max_steps = int(task.get("max_steps", 10))
        timeout = int(task.get("timeout_sec", 45))
        assert timeout >= max_steps * 8, f"Task {tid} timeout {timeout}s is too low for {max_steps} steps (must be >= {max_steps * 8}s)"


def test_pre_done_rejects_paint_title_spoof_notepad_plus_plus_and_wrong_calc_result() -> None:
    verifier = RuntimeGoalVerifier()

    # 1. Paint goal must not pass when only a non-mspaint window has "Paint" in its title
    non_paint_windows = [
        {"process_name": "chrome.exe", "title": "Open Paint - Google Gemini", "class_name": "Chrome_WidgetWin_1", "is_minimized": False},
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=non_paint_windows):
        res_paint = verifier.verify_goal_state("Open Paint")
        assert res_paint.verified is False
        assert "mspaint.exe" in res_paint.reason

    # 2. Notepad goal must not pass when only Notepad++ is open
    npp_windows = [
        {"process_name": "notepad++.exe", "title": "*new 1 - Notepad++", "class_name": "Notepad++", "is_minimized": False},
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=npp_windows):
        res_np = verifier.verify_goal_state("Open Notepad")
        assert res_np.verified is False
        assert "Notepad window is not open" in res_np.reason

    # 3. Calculator arithmetic goal must reject DONE when Calculator display does not show 56
    calc_windows = [
        {"process_name": "CalculatorApp.exe", "title": "Calculator", "class_name": "ApplicationFrameWindow", "is_minimized": False},
    ]
    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=calc_windows), \
         patch("parasite_ai.mind.verifier.read_calculator_display", return_value="Display is 0"):
        res_calc_bad = verifier.verify_goal_state("Open Calculator and compute 7 * 8")
        assert res_calc_bad.verified is False
        assert "56" in res_calc_bad.reason

    with patch("parasite_ai.mind.verifier.get_live_windows", return_value=calc_windows), \
         patch("parasite_ai.mind.verifier.read_calculator_display", return_value="Display is 56"):
        res_calc_ok = verifier.verify_goal_state("Open Calculator and compute 7 * 8")
        assert res_calc_ok.verified is True


def test_cleanup_benchmark_processes_releases_input_and_kills_lingering_parasite() -> None:
    import benchmarks.verifiers as bv

    with patch("benchmarks.verifiers.kill_lingering_parasite_processes") as mock_kill_p, \
         patch("benchmarks.verifiers.release_stuck_input_state") as mock_rel, \
         patch("benchmarks.verifiers.close_modal_dialogs") as mock_modal, \
         patch("benchmarks.verifiers.is_process_running", return_value=False), \
         patch("benchmarks.verifiers.minimize_non_target_monitor1_windows") as mock_min:
        bv.cleanup_benchmark_processes()

    mock_kill_p.assert_called_once()
    mock_rel.assert_called_once()
    mock_modal.assert_called_once()
    mock_min.assert_called_once()




