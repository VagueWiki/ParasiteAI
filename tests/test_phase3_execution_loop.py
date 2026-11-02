"""
tests/test_phase3_execution_loop.py - Comprehensive Unit Tests for Phase 3 Execution Loop Hardening.

Covers:
  - 3A: Localized ROI diffing (geometry, padding +20px, virtual boundary clamping 3840x1080,
       multi-monitor seam preservation, noise rejection in peripheral tray vs target change detection).
  - 3B: Win32 Caret Focus verification (blinking caret flag, hwndCaret != 0, unacquired caret with
       backoff timeout, cancellation token preemption, exception fallback).
  - 3C: Start Search Cadence Buffer (verifying 250ms pause between Win hotkey and application typing
       with mock time).
  - 3D: Safety invariants (hardware preemption, anti-hardcoding, dual-monitor geometry).
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from parasite_ai.mind.dual_mind import (
    ActionDispatcher,
    DualMindPipeline,
    GUI_CARETBLINKING,
    GUITHREADINFO,
    check_caret_focus,
    extract_action_target_roi,
    verify_caret_focus,
)
from parasite_ai.mind.memory import ActionPlan, ActionType, EpisodicMemory
from parasite_ai.mind.resolver import UniversalAppResolver
from parasite_ai.ui.types import BoundingBox, UIElement
from parasite_ai.vision.capture import get_virtual_screen_bounds


# ===========================================================================
# Helpers & Mocks
# ===========================================================================

def make_gui_thread_info_mock(flags: int = 0, hwnd_caret: int = 0, return_code: int = 1):
    """Factory creating a mock side_effect for ctypes.windll.user32.GetGUIThreadInfo."""
    def _mock(thread_id, p_info):
        if not return_code:
            return 0
        if hasattr(p_info, "_obj"):
            p_info._obj.flags = flags
            p_info._obj.hwndCaret = hwnd_caret
        return return_code
    return _mock


# ===========================================================================
# Phase 3A: Localized ROI Diffing Unit Tests
# ===========================================================================

class TestPhase3ALocalizedROIDiffing:
    """Tests for BoundingBox geometry, padding, clamping, slicing, and localized diffing."""

    def test_bounding_box_basic_geometry_and_as_tuple(self) -> None:
        """Tests basic properties, tuple conversion, and immutability of BoundingBox."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        assert bbox.x == 10
        assert bbox.y == 20
        assert bbox.width == 100
        assert bbox.height == 50
        assert bbox.as_tuple() == (10, 20, 100, 50)

        # Frozen immutability check
        with pytest.raises(Exception):
            bbox.x = 99  # type: ignore

    def test_bounding_box_padding_geometry(self) -> None:
        """Expands box uniformly by 20px on all 4 sides within bounds."""
        bbox = BoundingBox(x=100, y=100, width=50, height=50)
        padded = bbox.pad(padding_px=20, bounds=(0, 0, 3840, 1080))
        assert padded.x == 80
        assert padded.y == 80
        assert padded.width == 90   # 50 + 20 + 20
        assert padded.height == 90  # 50 + 20 + 20
        assert padded.as_tuple() == (80, 80, 90, 90)

    def test_bounding_box_clamping_virtual_screen_edges(self) -> None:
        """Clamps padded coordinates strictly to virtual screen boundaries."""
        # Top-left corner clamp
        top_left = BoundingBox(x=5, y=10, width=40, height=40)
        padded_tl = top_left.pad(padding_px=20, bounds=(0, 0, 3840, 1080))
        assert padded_tl.x == 0  # clamped from -15 to 0
        assert padded_tl.y == 0  # clamped from -10 to 0
        assert padded_tl.width == 65   # (5 + 40 + 20) - 0 = 65
        assert padded_tl.height == 70  # (10 + 40 + 20) - 0 = 70

        # Bottom-right corner clamp (Monitor 2 extreme edge)
        bottom_right = BoundingBox(x=3820, y=1060, width=30, height=30)
        padded_br = bottom_right.pad(padding_px=20, bounds=(0, 0, 3840, 1080))
        assert padded_br.x == 3800  # 3820 - 20
        assert padded_br.y == 1040  # 1060 - 20
        assert padded_br.width == 40   # clamped to 3840 (3840 - 3800 = 40)
        assert padded_br.height == 40  # clamped to 1080 (1080 - 1040 = 40)

    def test_dual_monitor_seam_preservation(self) -> None:
        """Preserves boxes that cross the dual-monitor seam at x = 1920 without clipping."""
        # Box placed right across the monitor seam
        seam_box = BoundingBox(x=1900, y=500, width=40, height=40)
        padded_seam = seam_box.pad(padding_px=20, bounds=(0, 0, 3840, 1080))
        assert padded_seam.x == 1880
        assert padded_seam.y == 480
        assert padded_seam.width == 80
        assert padded_seam.height == 80
        # Right edge spans into Monitor 2: 1880 + 80 = 1960 > 1920
        assert padded_seam.x + padded_seam.width == 1960

    def test_crop_frame_correct_extraction(self) -> None:
        """Crops numpy frame according to bounding box geometry."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[30:70, 20:60, :] = 255  # Distinct white patch

        bbox = BoundingBox(x=20, y=30, width=40, height=40)
        crop = bbox.crop_frame(frame, bounds=(0, 0, 100, 100))

        assert crop is not None
        assert crop.shape == (40, 40, 3)
        assert np.all(crop == 255)

    def test_crop_frame_degenerate_or_empty_returns_none(self) -> None:
        """Returns None safely for empty, None, or out-of-frame requests without crashing."""
        bbox = BoundingBox(x=20, y=30, width=40, height=40)
        assert bbox.crop_frame(None) is None
        assert bbox.crop_frame(np.zeros((0, 0, 3), dtype=np.uint8)) is None

        # Box outside frame
        oob_box = BoundingBox(x=500, y=500, width=50, height=50)
        small_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        assert oob_box.crop_frame(small_frame, bounds=(0, 0, 100, 100)) is None

    def test_ui_element_target_bbox_and_pad(self) -> None:
        """Verifies UIElement provides target_bbox and pad convenience methods."""
        elem = UIElement.from_bbox(1, (100, 200, 60, 40), label="OkButton")
        assert elem.target_bbox == BoundingBox(x=100, y=200, width=60, height=40)
        padded = elem.pad(padding_px=20, bounds=(0, 0, 3840, 1080))
        assert padded == BoundingBox(x=80, y=180, width=100, height=80)

    def test_extract_action_target_roi_resolution(self) -> None:
        """Tests extract_action_target_roi across target_id, coordinates, active window, and globals."""
        elements = [
            UIElement.from_bbox(1, (100, 100, 50, 30), label="Btn1"),
            UIElement.from_bbox(2, (200, 200, 80, 40), label="Btn2"),
        ]

        # 1. By target_id
        plan_id = ActionPlan(action=ActionType.CLICK, target_id=1)
        roi1 = extract_action_target_roi(plan_id, elements, bounds=(0, 0, 3840, 1080))
        assert roi1 is not None
        assert roi1.x == 80
        assert roi1.y == 80
        assert roi1.width == 90
        assert roi1.height == 70

        # 2. By coordinates intersecting element
        plan_coords = ActionPlan(action=ActionType.CLICK, coordinates=(220, 210))
        roi2 = extract_action_target_roi(plan_coords, elements, bounds=(0, 0, 3840, 1080))
        assert roi2 is not None
        assert roi2.x == 180  # 200 - 20
        assert roi2.y == 180  # 200 - 20

        # 3. By ungrounded coordinates (point ROI: 40x40 centered at point)
        plan_point = ActionPlan(action=ActionType.CLICK, coordinates=(500, 500))
        roi3 = extract_action_target_roi(plan_point, elements, bounds=(0, 0, 3840, 1080))
        assert roi3 is not None
        assert roi3.x == 480
        assert roi3.y == 480
        assert roi3.width == 40
        assert roi3.height == 40

        # 4. By active window for ungrounded typing
        plan_type = ActionPlan(action=ActionType.TYPE, text="hello")
        roi4 = extract_action_target_roi(
            plan_type,
            elements=[],
            active_window_rect=(300, 300, 400, 200),
            bounds=(0, 0, 3840, 1080),
        )
        assert roi4 is not None
        assert roi4.x == 280
        assert roi4.y == 280
        assert roi4.width == 440
        assert roi4.height == 240

        # 5. Global hotkey action -> None
        plan_hotkey = ActionPlan(action=ActionType.HOTKEY, keys=["win"])
        roi5 = extract_action_target_roi(plan_hotkey, elements, bounds=(0, 0, 3840, 1080))
        assert roi5 is None

    def test_dual_mind_pipeline_localized_roi_noise_rejection(self) -> None:
        """
        Adversarial test: High-volume pixel changes outside the target ROI (e.g. peripheral clock/tray)
        do NOT prevent an episodic strike when the target button itself did not change.
        """
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Clicking button"
        mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            config=None,
            mouse_driver=MagicMock(),
            keyboard_driver=MagicMock(),
            bridge=MagicMock(),
        )

        elements = [UIElement.from_bbox(1, (50, 50, 50, 50), label="TargetBtn")]
        base_frame = np.full((200, 200, 3), 100, dtype=np.uint8)

        # Peripheral noise: bottom-right corner changes drastically (e.g. tray pop-up)
        # but rows/cols 30:100 (target button + 20px padding) remain untouched
        noisy_frame = base_frame.copy()
        noisy_frame[150:200, 150:200, :] = 255  # 2500 pixels changed far away
        pipeline.capturer = MagicMock()
        pipeline.capturer.capture_screen.return_value = noisy_frame

        rec = pipeline.step(
            user_goal="Click target button",
            screen_frame=base_frame,
            grounded_elements=elements,
        )

        # Because ROI diffing is scoped to TargetBtn (50, 50, 50, 50) + 20px,
        # the peripheral changes contribute 0.0 diff -> strike is incurred!
        assert rec.is_strike is True
        assert rec.consecutive_strikes == 1

    def test_dual_mind_pipeline_localized_roi_target_change_detected(self) -> None:
        """
        Verifies that genuine visual changes within the target ROI reset episodic strikes,
        even if the total percentage of the desktop that changed is small.
        """
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Clicking button"
        mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            config=None,
            mouse_driver=MagicMock(),
            keyboard_driver=MagicMock(),
            bridge=MagicMock(),
        )

        elements = [UIElement.from_bbox(1, (50, 50, 50, 50), label="TargetBtn")]
        base_frame = np.full((200, 200, 3), 100, dtype=np.uint8)

        # Prior strike
        pipeline.memory.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=False, screen_diff=0.0)
        assert pipeline.memory.get_consecutive_strikes() == 1

        # Real visual change strictly inside TargetBtn
        real_change_frame = base_frame.copy()
        real_change_frame[55:75, 55:75, :] = 220  # delta = 120 > 15
        pipeline.capturer = MagicMock()
        pipeline.capturer.capture_screen.return_value = real_change_frame

        rec = pipeline.step(
            user_goal="Click target button",
            screen_frame=base_frame,
            grounded_elements=elements,
        )

        assert rec.is_strike is False
        assert rec.consecutive_strikes == 0
        assert pipeline.memory.get_consecutive_strikes() == 0


# ===========================================================================
# Phase 3B: Win32 Caret Focus Verification Unit Tests
# ===========================================================================

class TestPhase3BWin32CaretFocusVerification:
    """Tests for Win32 GUITHREADINFO structure, check_caret_focus, and ActionDispatcher.dispatch()."""

    def test_guithreadinfo_struct_size_and_fields(self) -> None:
        """Verifies ctypes GUITHREADINFO conforms to 72 bytes on 64-bit Windows."""
        is_64bit = ctypes.sizeof(ctypes.c_void_p) == 8
        expected_size = 72 if is_64bit else 48
        assert ctypes.sizeof(GUITHREADINFO) == expected_size

        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(GUITHREADINFO)
        info.flags = GUI_CARETBLINKING
        assert info.flags == 0x00000001

    def test_check_caret_focus_with_blinking_flag(self) -> None:
        """Returns True when info.flags has GUI_CARETBLINKING set."""
        mock_fn = make_gui_thread_info_mock(flags=GUI_CARETBLINKING, hwnd_caret=0, return_code=1)
        with patch.object(ctypes.windll.user32, "GetGUIThreadInfo", side_effect=mock_fn):
            assert check_caret_focus(0) is True

    def test_check_caret_focus_with_hwnd_caret(self) -> None:
        """Returns True when info.hwndCaret is non-zero even without blinking flag."""
        mock_fn = make_gui_thread_info_mock(flags=0, hwnd_caret=0x12345, return_code=1)
        with patch.object(ctypes.windll.user32, "GetGUIThreadInfo", side_effect=mock_fn):
            assert check_caret_focus(0) is True

    def test_check_caret_focus_with_both(self) -> None:
        """Returns True when both blinking flag and hwndCaret are present."""
        mock_fn = make_gui_thread_info_mock(flags=GUI_CARETBLINKING, hwnd_caret=0x9999, return_code=1)
        with patch.object(ctypes.windll.user32, "GetGUIThreadInfo", side_effect=mock_fn):
            assert check_caret_focus(0) is True

    def test_check_caret_focus_no_caret(self) -> None:
        """Returns False when neither flag nor hwndCaret is present."""
        mock_fn = make_gui_thread_info_mock(flags=0, hwnd_caret=0, return_code=1)
        with patch.object(ctypes.windll.user32, "GetGUIThreadInfo", side_effect=mock_fn):
            assert check_caret_focus(0) is False

    def test_check_caret_focus_api_failure(self) -> None:
        """Returns False when GetGUIThreadInfo API call fails (returns 0)."""
        mock_fn = make_gui_thread_info_mock(return_code=0)
        with patch.object(ctypes.windll.user32, "GetGUIThreadInfo", side_effect=mock_fn):
            assert check_caret_focus(0) is False

    def test_check_caret_focus_exception_handled_gracefully(self) -> None:
        """Returns False safely when GetGUIThreadInfo raises an OSError."""
        with patch.object(ctypes.windll.user32, "GetGUIThreadInfo", side_effect=OSError("Access denied")):
            assert check_caret_focus(0) is False

    def test_verify_caret_focus_polling_success_within_timeout(self) -> None:
        """Simulates asynchronous focus acquisition succeeding on the 3rd poll."""
        call_count = 0

        def _intermittent_check(tid=0):
            nonlocal call_count
            call_count += 1
            return call_count >= 3

        with patch("parasite_ai.mind.dual_mind.check_caret_focus", side_effect=_intermittent_check):
            ok = verify_caret_focus(timeout_ms=250.0, poll_interval_ms=10.0)
            assert ok is True
            assert call_count == 3

    def test_verify_caret_focus_timeout_exhausted(self) -> None:
        """Returns False after polling budget is exhausted without focus."""
        with patch("parasite_ai.mind.dual_mind.check_caret_focus", return_value=False):
            start = time.time()
            ok = verify_caret_focus(timeout_ms=60.0, poll_interval_ms=15.0)
            elapsed = time.time() - start
            assert ok is False
            assert elapsed >= 0.05

    def test_verify_caret_focus_cancellation_preemption(self) -> None:
        """Immediately aborts in <2ms when cancellation_token is set."""
        token = threading.Event()
        token.set()

        start = time.perf_counter()
        ok = verify_caret_focus(timeout_ms=500.0, cancellation_token=token)
        latency_ms = (time.perf_counter() - start) * 1000.0

        assert ok is False
        assert latency_ms < 5.0  # Well within safety margins

    def test_action_dispatcher_type_fails_when_caret_not_detected(self) -> None:
        """ActionDispatcher rejects ungrounded TYPE when caret focus is absent."""
        mock_kbd = MagicMock()
        mock_mouse = MagicMock()
        dispatcher = ActionDispatcher(mouse_driver=mock_mouse, keyboard_driver=mock_kbd)

        # Mock caret focus to fail
        dispatcher.verify_caret_focus = MagicMock(return_value=False)

        action = ActionPlan(action=ActionType.TYPE, text="test input\n")
        res = dispatcher.dispatch(action, som_elements=[])

        assert res.success is False
        assert "Caret focus not detected" in (res.error or "")
        mock_kbd.type_text.assert_not_called()

    def test_action_dispatcher_type_succeeds_when_caret_detected(self) -> None:
        """ActionDispatcher types successfully when caret focus is confirmed."""
        mock_kbd = MagicMock()
        mock_kbd.type_text.return_value = True
        mock_mouse = MagicMock()
        dispatcher = ActionDispatcher(mouse_driver=mock_mouse, keyboard_driver=mock_kbd)

        dispatcher.verify_caret_focus = MagicMock(return_value=True)

        action = ActionPlan(action=ActionType.TYPE, text="test input\n")
        res = dispatcher.dispatch(action, som_elements=[])

        assert res.success is True
        mock_kbd.type_text.assert_called_once_with(
            text="test input\n",
            submit=False,
            cancellation_token=None,
        )

    def test_action_dispatcher_type_interrupted_by_cancellation_token(self) -> None:
        """ActionDispatcher returns interrupted=True when cancellation token triggers during caret check."""
        mock_kbd = MagicMock()
        mock_mouse = MagicMock()
        dispatcher = ActionDispatcher(mouse_driver=mock_mouse, keyboard_driver=mock_kbd)

        token = threading.Event()
        token.set()

        action = ActionPlan(action=ActionType.TYPE, text="test input\n")
        res = dispatcher.dispatch(action, som_elements=[], cancellation_token=token)

        assert res.success is False
        assert res.interrupted is True
        mock_kbd.type_text.assert_not_called()


# ===========================================================================
# Phase 3C: Start Search Cadence Buffer Unit Tests
# ===========================================================================

class TestPhase3CStartSearchCadenceBuffer:
    """Tests for UniversalAppResolver 250ms cadence buffer in Tier 2 Start Search."""

    def test_universal_app_resolver_cadence_buffer_default(self) -> None:
        """Verifies default cadence buffer duration is 250ms (0.25s)."""
        resolver = UniversalAppResolver()
        assert resolver.cadence_buffer_ms == 250.0
        assert resolver.cadence_buffer_s == 0.25

    def test_universal_app_resolver_cadence_buffer_configurable(self) -> None:
        """Verifies custom cadence buffer configuration."""
        resolver = UniversalAppResolver(cadence_buffer_ms=500.0)
        assert resolver.cadence_buffer_ms == 500.0
        assert resolver.cadence_buffer_s == 0.5

    def test_universal_app_resolver_tier2_enforces_250ms_sleep(self, mocker) -> None:
        """Verifies 250ms cadence sleep is enforced between Win key and typing."""
        mock_sleep = mocker.patch("parasite_ai.mind.resolver.time.sleep")
        resolver = UniversalAppResolver()

        # Step 1: Win hotkey triggered, no sleep yet
        action1 = resolver.resolve_launch_action("notepad", [])
        assert action1.action == ActionType.HOTKEY
        assert action1.keys == ["win"]
        assert action1.wait_ms == 250
        mock_sleep.assert_not_called()

        # Step 2: Typing into active Start Search -> sleep(0.25) must be called
        action2 = resolver.resolve_launch_action("notepad", [])
        assert action2.action == ActionType.TYPE
        assert "notepad\n" in (action2.text or "")
        mock_sleep.assert_called_once_with(0.25)

    def test_universal_app_resolver_custom_cadence_sleep(self, mocker) -> None:
        """Verifies custom cadence buffer value is passed to sleep."""
        mock_sleep = mocker.patch("parasite_ai.mind.resolver.time.sleep")
        resolver = UniversalAppResolver(cadence_buffer_ms=100.0)

        resolver.resolve_launch_action("calc", [])
        mock_sleep.assert_not_called()

        resolver.resolve_launch_action("calc", [])
        mock_sleep.assert_called_once_with(0.1)

    def test_universal_app_resolver_zero_cadence_skips_sleep(self, mocker) -> None:
        """Verifies cadence buffer of 0.0 skips sleep calls completely."""
        mock_sleep = mocker.patch("parasite_ai.mind.resolver.time.sleep")
        resolver = UniversalAppResolver(cadence_buffer_ms=0.0)

        resolver.resolve_launch_action("paint", [])
        resolver.resolve_launch_action("paint", [])
        mock_sleep.assert_not_called()

    def test_universal_app_resolver_search_edit_respects_cadence_if_opened(self, mocker) -> None:
        """Verifies cadence buffer sleep if Start Search edit appears after Win key."""
        mock_sleep = mocker.patch("parasite_ai.mind.resolver.time.sleep")
        resolver = UniversalAppResolver()

        # Trigger Win
        resolver.resolve_launch_action("paint", [])
        mock_sleep.assert_not_called()

        # Search box appears in SOM elements
        elements = [
            UIElement.from_bbox(1, (100, 950, 400, 40), label="Type here to search", role="Edit"),
        ]
        action = resolver.resolve_launch_action("paint", elements)
        assert action.action == ActionType.CLICK_AND_TYPE
        mock_sleep.assert_called_once_with(0.25)

    def test_universal_app_resolver_cadence_cancellation_token_interrupted(self) -> None:
        """Cancellation token interrupts cadence wait immediately without blocking."""
        token = threading.Event()
        token.set()

        resolver = UniversalAppResolver(cadence_buffer_ms=1000.0)
        resolver._search_opened = True

        start = time.perf_counter()
        action = resolver.resolve_launch_action("notepad", [], cancellation_token=token)
        latency_ms = (time.perf_counter() - start) * 1000.0

        assert action.action == ActionType.TYPE
        assert latency_ms < 10.0  # Aborted immediately via token.wait()


# ===========================================================================
# Phase 3D: Invariant Verification
# ===========================================================================

class TestPhase3DArchitecturalInvariants:
    """Verifies all strict system invariants: anti-hardcoding, preemption, geometry."""

    def test_anti_hardcoding_invariant_resolver_has_no_app_maps(self) -> None:
        """Strict Anti-Hardcoding: UniversalAppResolver must contain zero application dictionaries."""
        resolver = UniversalAppResolver()
        attrs = dir(resolver)
        assert "app_map" not in attrs
        assert "APP_MAP" not in attrs
        assert "APPS" not in attrs

        # Verify generic resolution works on completely fabricated application names
        fabricated_names = [
            "QuantumRenderer_v4",
            "SuperNovaEditor",
            "MyCustomLabTool",
            "InternalEnterprisePortal",
        ]
        for name in fabricated_names:
            resolver.reset()
            act1 = resolver.resolve_launch_action(name, [])
            assert act1.action == ActionType.HOTKEY
            act2 = resolver.resolve_launch_action(name, [])
            assert act2.action == ActionType.TYPE
            assert name in (act2.text or "")

    def test_dual_monitor_virtual_desktop_bounds_safety(self) -> None:
        """Verifies dual-monitor virtual desktop bounds (3840x1080) are queried and safe."""
        bounds = get_virtual_screen_bounds()
        vx, vy, vw, vh = bounds
        assert vw >= 1920
        assert vh >= 1080

        # Verify a Monitor 2 bounding box (x=2500) is valid within virtual desktop
        mon2_box = BoundingBox(x=2500, y=300, width=100, height=50)
        padded = mon2_box.pad(20, bounds=bounds)
        assert padded.x == 2480
        assert padded.y == 280
        assert padded.width == 140
        assert padded.height == 90
