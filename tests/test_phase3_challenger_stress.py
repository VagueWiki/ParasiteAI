"""
tests/test_phase3_challenger_stress.py - Empirical Challenger Stress Harness for Requirement R1.

Adversarial stress-testing of Phase 3A Localized ROI Diffing:
1. Extreme boundary conditions:
   - Elements partially off-screen (x=-10, y=0, width=50, height=50).
   - Seam-crossing elements spanning Monitor 1 and Monitor 2 (x=1910 crossing 1920 seam).
   - Extreme bottom-right corner of virtual desktop (x=3830, y=1070).
   - Zero-width or zero-height elements.
2. Peripheral noise rejection:
   - System tray change emulation (x=3800, y=1050) while clicking Monitor 1 target (x=200, y=200).
     Verifies 0.0 diff and strike recording.
   - Target ROI visual change emulation; verifies diff exceeds threshold and resets strikes to 0.
3. Fallback behavior:
   - Ungrounded point clicks produce centered 40x40 padded ROI.
   - Global actions (HOTKEY, WAIT, DONE, PANIC) fall back cleanly to full desktop diffing without errors.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import numpy as np
import pytest

from parasite_ai.mind.dual_mind import (
    DualMindPipeline,
    extract_action_target_roi,
)
from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.ui.types import BoundingBox, UIElement


# ===========================================================================
# 1. Extreme Boundary Conditions for BoundingBox.pad(20px)
# ===========================================================================

class TestExtremeBoundaryConditions:
    """Stress tests extreme geometric coordinates and multi-monitor boundaries."""

    VIRTUAL_BOUNDS = (0, 0, 3840, 1080)

    def test_partially_offscreen_left_top_element(self) -> None:
        """
        Element partially off-screen: x=-10, y=0, width=50, height=50.
        Padded by 20px, clamped to screen bounds (0, 0, 3840, 1080).
        """
        box = BoundingBox(x=-10, y=0, width=50, height=50)
        padded = box.pad(padding_px=20, bounds=self.VIRTUAL_BOUNDS)

        # Expected:
        # new_x = max(0, -10 - 20) = 0
        # new_y = max(0, 0 - 20) = 0
        # new_right = min(3840, -10 + 50 + 20) = 60
        # new_bottom = min(1080, 0 + 50 + 20) = 70
        # new_w = 60 - 0 = 60
        # new_h = 70 - 0 = 70
        assert padded.x == 0
        assert padded.y == 0
        assert padded.width == 60
        assert padded.height == 70

        # Verify crop from full 3840x1080 frame
        frame = np.zeros((1080, 3840, 3), dtype=np.uint8)
        frame[0:70, 0:60, :] = 128
        crop = padded.crop_frame(frame, bounds=self.VIRTUAL_BOUNDS)
        assert crop is not None
        assert crop.shape == (70, 60, 3)
        assert np.all(crop == 128)

    def test_completely_offscreen_element_safely_degenerates(self) -> None:
        """
        Element completely off-screen: x=-200, y=-200, width=50, height=50.
        Padded by 20px should clamp to width=0, height=0 and crop_frame return None.
        """
        box = BoundingBox(x=-200, y=-200, width=50, height=50)
        padded = box.pad(padding_px=20, bounds=self.VIRTUAL_BOUNDS)
        assert padded.x == 0
        assert padded.y == 0
        assert padded.width == 0
        assert padded.height == 0

        frame = np.zeros((1080, 3840, 3), dtype=np.uint8)
        crop = padded.crop_frame(frame, bounds=self.VIRTUAL_BOUNDS)
        assert crop is None

    def test_dual_monitor_seam_crossing_element(self) -> None:
        """
        Element on boundary of Monitor 1 and Monitor 2:
        x=1910, y=500, width=50, height=50 (crossing the 1920 seam).
        """
        box = BoundingBox(x=1910, y=500, width=50, height=50)
        padded = box.pad(padding_px=20, bounds=self.VIRTUAL_BOUNDS)

        # Expected:
        # new_x = max(0, 1910 - 20) = 1890 (in Monitor 1)
        # new_y = max(0, 500 - 20) = 480
        # new_right = min(3840, 1910 + 50 + 20) = 1980 (in Monitor 2)
        # new_bottom = min(1080, 500 + 50 + 20) = 570
        # new_w = 1980 - 1890 = 90
        # new_h = 570 - 480 = 90
        assert padded.x == 1890
        assert padded.y == 480
        assert padded.width == 90
        assert padded.height == 90
        assert padded.x < 1920  # Left edge on Monitor 1
        assert (padded.x + padded.width) > 1920  # Right edge on Monitor 2

        # Empirical crop verification across seam
        frame = np.zeros((1080, 3840, 3), dtype=np.uint8)
        # Put Monitor 1 pixels as 100, Monitor 2 pixels as 200
        frame[480:570, 1890:1920, :] = 100
        frame[480:570, 1920:1980, :] = 200
        crop = padded.crop_frame(frame, bounds=self.VIRTUAL_BOUNDS)

        assert crop is not None
        assert crop.shape == (90, 90, 3)
        # First 30 columns belong to Monitor 1 (1890 to 1920)
        assert np.all(crop[:, :30, :] == 100)
        # Remaining 60 columns belong to Monitor 2 (1920 to 1980)
        assert np.all(crop[:, 30:, :] == 200)

    def test_extreme_bottom_right_virtual_desktop_element(self) -> None:
        """
        Element at the extreme bottom-right of the virtual desktop:
        x=3830, y=1070, width=50, height=50.
        Padded by 20px, clamped to max 3840x1080.
        """
        box = BoundingBox(x=3830, y=1070, width=50, height=50)
        padded = box.pad(padding_px=20, bounds=self.VIRTUAL_BOUNDS)

        # Expected:
        # new_x = max(0, 3830 - 20) = 3810
        # new_y = max(0, 1070 - 20) = 1050
        # new_right = min(3840, 3830 + 50 + 20) = 3840
        # new_bottom = min(1080, 1070 + 50 + 20) = 1080
        # new_w = 3840 - 3810 = 30
        # new_h = 1080 - 1050 = 30
        assert padded.x == 3810
        assert padded.y == 1050
        assert padded.width == 30
        assert padded.height == 30

        # Verify crop from full 3840x1080 frame
        frame = np.zeros((1080, 3840, 3), dtype=np.uint8)
        frame[1050:1080, 3810:3840, :] = 210
        crop = padded.crop_frame(frame, bounds=self.VIRTUAL_BOUNDS)
        assert crop is not None
        assert crop.shape == (30, 30, 3)
        assert np.all(crop == 210)

    def test_zero_width_or_zero_height_elements(self) -> None:
        """
        Zero-width or zero-height elements should expand to 40px in degenerate dimension
        under 20px padding without errors.
        """
        # Point element (0x0)
        point = BoundingBox(x=500, y=400, width=0, height=0)
        padded_point = point.pad(padding_px=20, bounds=self.VIRTUAL_BOUNDS)
        assert padded_point.x == 480
        assert padded_point.y == 380
        assert padded_point.width == 40
        assert padded_point.height == 40

        # Zero-width line element (0x50)
        v_line = BoundingBox(x=300, y=200, width=0, height=50)
        padded_vline = v_line.pad(padding_px=20, bounds=self.VIRTUAL_BOUNDS)
        assert padded_vline.x == 280
        assert padded_vline.y == 180
        assert padded_vline.width == 40
        assert padded_vline.height == 90

        # Zero-height line element (50x0)
        h_line = BoundingBox(x=300, y=200, width=50, height=0)
        padded_hline = h_line.pad(padding_px=20, bounds=self.VIRTUAL_BOUNDS)
        assert padded_hline.x == 280
        assert padded_hline.y == 180
        assert padded_hline.width == 90
        assert padded_hline.height == 40


# ===========================================================================
# 2. Peripheral Noise Rejection & Strike Reset
# ===========================================================================

class TestPeripheralNoiseRejection:
    """Stress tests noise rejection in system tray vs genuine target ROI changes."""

    def test_peripheral_tray_noise_yields_zero_diff_and_strike(self) -> None:
        """
        Emulate changes in system tray (x=3800, y=1050 on Monitor 2)
        while clicking a target element on Monitor 1 (x=200, y=200, width=50, height=50).
        Verifies localized ROI diffing yields 0.0 diff and records a strike.
        """
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Clicking button on Monitor 1"
        mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            config=None,
            mouse_driver=MagicMock(),
            keyboard_driver=MagicMock(),
            bridge=MagicMock(),
        )

        elements = [
            UIElement.from_bbox(1, (200, 200, 50, 50), label="Monitor1Target")
        ]

        # 3840x1080 dual-monitor virtual desktop
        base_frame = np.full((1080, 3840, 3), 50, dtype=np.uint8)

        # Post frame: system tray at (3800, 1050) changes drastically (e.g. clock/toast)
        noisy_post_frame = base_frame.copy()
        noisy_post_frame[1040:1080, 3750:3840, :] = 255  # ~3600 pixels changed far away

        pipeline.capturer = MagicMock()
        pipeline.capturer.capture_screen.return_value = noisy_post_frame

        rec = pipeline.step(
            user_goal="Click target on Monitor 1",
            screen_frame=base_frame,
            grounded_elements=elements,
        )

        # Verification: localized ROI diffing for Monitor 1 target must yield 0.0 diff
        assert rec.screen_diff == 0.0
        assert rec.is_strike is True
        assert rec.consecutive_strikes == 1
        assert pipeline.memory._consecutive_strikes == 1

    def test_changes_inside_target_roi_exceed_threshold_and_reset_strikes(self) -> None:
        """
        Emulate changes strictly inside target ROI on Monitor 1.
        Verifies diff exceeds threshold (>0.02) and resets strikes to 0.
        """
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Clicking button on Monitor 1"
        mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            config=None,
            mouse_driver=MagicMock(),
            keyboard_driver=MagicMock(),
            bridge=MagicMock(),
        )

        # Preload 2 consecutive strikes into memory
        pipeline.memory.record_step(
            action=ActionPlan(action=ActionType.CLICK, target_id=1),
            success=True,
            screen_diff=0.0,
        )
        pipeline.memory.record_step(
            action=ActionPlan(action=ActionType.CLICK, target_id=1),
            success=True,
            screen_diff=0.0,
        )
        assert pipeline.memory._consecutive_strikes == 2

        elements = [
            UIElement.from_bbox(1, (200, 200, 50, 50), label="Monitor1Target")
        ]

        base_frame = np.full((1080, 3840, 3), 50, dtype=np.uint8)

        # Target ROI changes strictly inside (200:250, 200:250)
        target_changed_frame = base_frame.copy()
        target_changed_frame[210:240, 210:240, :] = 240  # 900 pixels changed inside ROI

        pipeline.capturer = MagicMock()
        pipeline.capturer.capture_screen.return_value = target_changed_frame

        rec = pipeline.step(
            user_goal="Click target on Monitor 1",
            screen_frame=base_frame,
            grounded_elements=elements,
        )

        # Verification: diff exceeds 0.02 threshold and strikes reset to 0
        assert rec.screen_diff > 0.02
        assert rec.is_strike is False
        assert rec.consecutive_strikes == 0
        assert pipeline.memory._consecutive_strikes == 0


# ===========================================================================
# 3. Fallback Behavior
# ===========================================================================

class TestFallbackBehavior:
    """Stress tests fallback mechanics for ungrounded clicks and global actions."""

    VIRTUAL_BOUNDS = (0, 0, 3840, 1080)

    def test_ungrounded_point_clicks_create_centered_40x40_padded_roi(self) -> None:
        """
        Ungrounded point clicks must create a 40x40 padded ROI centered on the click coordinates.
        E.g. click at (600, 400) -> ROI at (580, 380, 40, 40).
        """
        action = ActionPlan(action=ActionType.CLICK, coordinates=(600, 400))
        roi = extract_action_target_roi(
            action=action,
            elements=[],
            bounds=self.VIRTUAL_BOUNDS,
            padding_px=20,
        )

        assert roi is not None
        assert roi.x == 580
        assert roi.y == 380
        assert roi.width == 40
        assert roi.height == 40

    def test_global_actions_cleanly_fallback_to_full_desktop_diffing(self) -> None:
        """
        Global actions (HOTKEY, WAIT, DONE, PANIC) return None for target ROI,
        cleanly falling back to full desktop diffing without raising errors.
        """
        # 1. HOTKEY action
        hotkey_action = ActionPlan(action=ActionType.HOTKEY, keys=["ctrl", "s"])
        roi_hotkey = extract_action_target_roi(
            action=hotkey_action,
            elements=[],
            bounds=self.VIRTUAL_BOUNDS,
        )
        assert roi_hotkey is None

        # 2. WAIT action
        wait_action = ActionPlan(action=ActionType.WAIT, wait_ms=500)
        roi_wait = extract_action_target_roi(
            action=wait_action,
            elements=[],
            bounds=self.VIRTUAL_BOUNDS,
        )
        assert roi_wait is None

        # 3. Execution loop test for global HOTKEY action
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Saving file via Ctrl+S"
        mock_brain.generate_action.return_value = {"action": "HOTKEY", "keys": ["ctrl", "s"]}

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            config=None,
            mouse_driver=MagicMock(),
            keyboard_driver=MagicMock(),
            bridge=MagicMock(),
        )

        base_frame = np.full((1080, 3840, 3), 50, dtype=np.uint8)
        changed_frame = base_frame.copy()
        # Status bar changed at bottom of screen
        changed_frame[1000:1040, 100:600, :] = 255

        # Test 1: HOTKEY with large change (>2% of desktop, e.g. window popup 500x200=100k px)
        changed_large = base_frame.copy()
        changed_large[200:700, 200:400, :] = 255  # 100,000 px / 4,147,200 px = 2.41% > 2%

        pipeline.capturer = MagicMock()
        pipeline.capturer.capture_screen.return_value = changed_large

        rec_large = pipeline.step(
            user_goal="Save document",
            screen_frame=base_frame,
            grounded_elements=[],
        )

        # Full desktop diffing was used without error and exceeded 2% threshold
        assert rec_large.screen_diff > 0.02
        assert rec_large.is_strike is False
        assert rec_large.consecutive_strikes == 0

        # Test 2: HOTKEY with zero change records a strike as expected
        pipeline.capturer.capture_screen.return_value = base_frame
        rec_zero = pipeline.step(
            user_goal="Save document",
            screen_frame=base_frame,
            grounded_elements=[],
        )
        assert rec_zero.screen_diff == 0.0
        assert rec_zero.is_strike is True
        assert rec_zero.consecutive_strikes == 1

        # Test 3: Non-interactive action (WAIT) does not record strikes even with 0.0 diff
        mock_brain.generate_action.return_value = {"action": "WAIT", "wait_ms": 500}
        rec_wait = pipeline.step(
            user_goal="Wait for page",
            screen_frame=base_frame,
            grounded_elements=[],
        )
        assert rec_wait.screen_diff == 0.0
        assert rec_wait.is_strike is False
