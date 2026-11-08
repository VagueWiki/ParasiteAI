"""
Tests for ParasiteAI Stint P1.3 — Single-Pass CUA Execution Path, Self-UI Exclusion & App Disambiguation.
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from parasite_ai.config import AppConfig
from parasite_ai.mind.brain_manager import BrainMode, LocalBrainManager
from parasite_ai.mind.dual_mind import DualMindPipeline, PersonaEngine
from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.mind.resolver import PrecisionAppMatcher
from parasite_ai.vision.grounding import RawElement, ScreenGrounder, UIElement


# ---------------------------------------------------------------------------
# 1. PrecisionAppMatcher Identifier Boundary Disambiguation Tests
# ---------------------------------------------------------------------------

def test_precision_app_matcher_boundary_matrix() -> None:
    """Verifies symbol and domain suffixes (+, #, .net) prevent false positive collisions."""
    # Suffix derivative collision rejection
    assert PrecisionAppMatcher.score_match("Notepad++", "Notepad") == 0.0
    assert PrecisionAppMatcher.score_match("notepad++", "notepad") == 0.0
    assert PrecisionAppMatcher.score_match("paint.net", "Paint") == 0.0
    assert PrecisionAppMatcher.score_match("Paint.NET", "Paint") == 0.0
    assert PrecisionAppMatcher.score_match("C++ Primer", "C") == 0.0
    assert PrecisionAppMatcher.score_match("C# Shell", "C") == 0.0

    # Exact matches
    assert PrecisionAppMatcher.score_match("Notepad++", "Notepad++") == 1.0
    assert PrecisionAppMatcher.score_match("notepad++", "notepad++") == 1.0
    assert PrecisionAppMatcher.score_match("Paint.NET", "Paint.NET") == 1.0
    assert PrecisionAppMatcher.score_match("paint.net", "paint.net") == 1.0

    # Legitimate substrings with standard word boundaries
    assert PrecisionAppMatcher.score_match("Untitled - Notepad", "Notepad") >= 0.80
    assert PrecisionAppMatcher.score_match("Document 1 - Paint", "Paint") >= 0.80
    assert PrecisionAppMatcher.score_match("new 1 - Notepad++", "Notepad++") >= 0.80


# ---------------------------------------------------------------------------
# 2. Self-UI & Self-PID Exclusion Invariant Tests
# ---------------------------------------------------------------------------

def test_screen_grounder_excludes_self_pid_and_companion() -> None:
    """Verifies that windows and controls belonging to os.getpid() or CompanionDock are filtered."""
    grounder = ScreenGrounder()
    mock_auto = MagicMock()

    cur_pid = os.getpid()
    foreign_pid = cur_pid + 9999

    # Create mock top-level children
    # 1. CompanionDock (self-UI overlay, docked at screen edge)
    mock_companion = MagicMock()
    mock_companion.ClassName = "CompanionDock"
    mock_companion.ProcessId = cur_pid
    mock_companion.NativeWindowHandle = 1001
    mock_companion.BoundingRectangle = SimpleNamespace(left=1500, top=800, right=1900, bottom=1050, width=400, height=250)

    # 2. ParasiteAI Launcher window (self-process)
    mock_self_win = MagicMock()
    mock_self_win.ClassName = "Window"
    mock_self_win.Name = "ParasiteAI Launcher"
    mock_self_win.ProcessId = cur_pid
    mock_self_win.NativeWindowHandle = 1002
    mock_self_win.BoundingRectangle = SimpleNamespace(left=50, top=50, right=500, bottom=400, width=450, height=350)

    # 3. Third-party target window (Notepad)
    mock_notepad = MagicMock()
    mock_notepad.ClassName = "Notepad"
    mock_notepad.Name = "Untitled - Notepad"
    mock_notepad.ProcessId = foreign_pid
    mock_notepad.NativeWindowHandle = 2001
    mock_notepad.BoundingRectangle = SimpleNamespace(left=200, top=200, right=800, bottom=700, width=600, height=500)

    mock_auto.GetForegroundControl.return_value = mock_notepad
    mock_auto.GetRootControl.return_value.GetChildren.return_value = [
        mock_companion,
        mock_self_win,
        mock_notepad,
    ]

    # Inner walk on Notepad
    mock_btn = MagicMock()
    mock_btn.Name = "File"
    mock_btn.ControlTypeName = "MenuItemControl"
    mock_btn.ClassName = "MenuItem"
    mock_btn.ProcessId = foreign_pid
    mock_btn.IsOffscreen = False
    mock_btn.NativeWindowHandle = 0
    mock_btn.BoundingRectangle = SimpleNamespace(left=210, top=230, right=250, bottom=260, width=40, height=30)

    # A rogue self-pid control inside the walk
    mock_rogue_self_ctrl = MagicMock()
    mock_rogue_self_ctrl.Name = "Speech Bubble"
    mock_rogue_self_ctrl.ControlTypeName = "TextControl"
    mock_rogue_self_ctrl.ClassName = "Text"
    mock_rogue_self_ctrl.ProcessId = cur_pid
    mock_rogue_self_ctrl.IsOffscreen = False
    mock_rogue_self_ctrl.NativeWindowHandle = 0
    mock_rogue_self_ctrl.BoundingRectangle = SimpleNamespace(left=150, top=150, right=250, bottom=200, width=100, height=50)

    mock_auto.WalkControl.return_value = [
        (mock_btn, 1),
        (mock_rogue_self_ctrl, 1),
    ]

    with patch.object(ScreenGrounder, "_is_hwnd_visible_and_uncloaked", return_value=True):
        raw_elements, active_rect = grounder._walk_uia_tree_inner(mock_auto)

    # Assertions
    labels = [e.label for e in raw_elements]
    assert "File" in labels
    assert "Speech Bubble" not in labels, "Rogue control from os.getpid() must be excluded"
    assert "ParasiteAI Launcher" not in labels, "Self-process top-level window must be excluded"
    assert grounder._last_excluded_rect == (1500, 800, 1900, 1050), "CompanionDock bounds must be recorded as excluded_rect"


def test_scoped_ocr_excludes_companion_dock_bounds() -> None:
    """Verifies that RapidOCR detections inside _last_excluded_rect are masked out."""
    grounder = ScreenGrounder()
    grounder._last_excluded_rect = (100, 100, 400, 300)

    # Mock OCR engine returning one box inside excluded_rect and one outside
    mock_engine = MagicMock()
    mock_engine.return_value = [
        # Inside CompanionDock (center 200, 150):
        ([[150, 140], [250, 140], [250, 160], [150, 160]], "Ah looking at the scene", 0.95),
        # Outside CompanionDock (center 500, 500):
        ([[450, 490], [550, 490], [550, 510], [450, 510]], "Legitimate Target Text", 0.95),
    ]
    grounder._ocr_engine = mock_engine

    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    ocr_elements = grounder._run_scoped_ocr(window_rect=(0, 0, 1280, 720), image_override=dummy_frame)

    ocr_labels = [e.label for e in ocr_elements]
    assert "Legitimate Target Text" in ocr_labels
    assert "Ah looking at the scene" not in ocr_labels, "Speech bubble OCR text must be suppressed"


# ---------------------------------------------------------------------------
# 3. LocalBrainManager.generate_cua_step Tests
# ---------------------------------------------------------------------------

def test_brain_manager_generate_cua_step() -> None:
    """Verifies generate_cua_step executes single multimodal completion and parses via uitars_parser."""
    cfg = AppConfig()
    mgr = LocalBrainManager(cfg)

    mock_backend = MagicMock()
    mock_backend.is_available.return_value = True
    mock_backend.supports_vision.return_value = True
    mock_backend.generate.return_value = (
        "Thought: I see the Save button in the Notepad toolbar. Clicking it.\n"
        "Action: click(start_box='(500, 200)')"
    )
    mgr.active_backend = mock_backend
    mgr.mode = BrainMode.LOCAL_LLM

    dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    thought, plan = mgr.generate_cua_step(
        user_goal="Save document",
        screen_frame=dummy_frame,
        screen_width=1920,
        screen_height=1080,
    )

    assert mock_backend.generate.call_count == 1, "Must execute in exactly ONE LLM call"
    assert "Save button" in thought
    assert plan.action == ActionType.CLICK
    assert plan.coordinates == (960, 216)


# ---------------------------------------------------------------------------
# 4. DualMindPipeline Single-Pass CUA Execution Tests
# ---------------------------------------------------------------------------

def test_dual_mind_single_pass_cua_path() -> None:
    """Verifies DualMindPipeline.step() uses generate_cua_step and bypasses Pass 1/2 double call."""
    from parasite_ai.mind.dual_mind import ActionResult

    mock_brain = MagicMock()
    mock_brain.supports_vision.return_value = True
    planned_act = ActionPlan(action=ActionType.CLICK, coordinates=(25, 980), reasoning="Click Start")
    mock_brain.generate_cua_step.return_value = (
        "Opening Notepad via Start menu.",
        planned_act,
    )

    pipeline = DualMindPipeline(brain_manager=mock_brain)
    pipeline.persona_engine = MagicMock(spec=PersonaEngine)

    dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    with patch.object(
        pipeline.action_dispatcher,
        "dispatch",
        return_value=ActionResult(success=True, action_executed=planned_act),
    ):
        step_rec = pipeline.step(
            user_goal="Open Notepad",
            screen_frame=dummy_frame,
        )

    # 1. CUA single-pass step was called
    mock_brain.generate_cua_step.assert_called_once()
    # 2. Legacy Pass 1 monologue was bypassed
    pipeline.persona_engine.generate_monologue.assert_not_called()
    # 3. Legacy Pass 2 generate_action was bypassed
    mock_brain.generate_action.assert_not_called()

    # 4. Step record captured thought as persona speech
    assert step_rec.action.action == ActionType.CLICK
    assert step_rec.action.coordinates == (25, 980)
    assert step_rec.persona_speech == "Opening Notepad via Start menu."
