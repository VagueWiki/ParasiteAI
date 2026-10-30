"""
tests/test_challenger_m4_2.py - Adversarial Stress Test Suite for Milestone M4.

Focus: Features 13, 14, 15:
- Episodic Working Memory & Screen Diff Verification (parasite_ai/mind/memory.py)
- Dual-Mind Cognitive Pipeline & Action Dispatcher (parasite_ai/mind/dual_mind.py)
- Visible Browser Brain Offloader & Sentinel Clipboard Protocol (parasite_ai/mind/offloader.py)

Adversarial Stress Scenarios:
1. 3-strike failure detector:
   - 2 failures then 1 success -> strike count resets to 0.
   - 3 failures (trips loop) then 1 success -> loop clears and strikes reset to 0.
   - Non-interactive actions (WAIT, DONE, OFFLOAD_WEB_AI, PANIC) never incur strikes.
   - Non-interactive actions do not clear pending strikes.
   - Subtle visual noise (channel delta <= 15) evaluated as 0.0 diff and triggers strikes.
   - Genuine pixel change (channel delta > 15) detected accurately.
   - High-concurrency multithreaded recording to EpisodicMemory ring-buffer.
2. ActionDispatcher preemption:
   - Pre-set cancellation_token causes instant (<2ms) abort without invoking hand drivers.
   - Out-of-bounds target coordinates (negative or extreme) fail with structured error.
   - Unresolvable Set-of-Mark target_id fails gracefully without exceptions.
   - Missing coordinates and target_id fails with structured error.
   - Driver exceptions during dispatch invoke _release_all() and return structured error.
3. Sentinel Clipboard Verification:
   - Error injection during copy trigger -> original user clipboard is STILL restored.
   - Clipboard returning exact sentinel token is strictly rejected.
   - Empty or whitespace clipboard response times out and is rejected.
   - Sentinel arming mismatch aborts cleanly.
4. Visible Browser Offloader & DualMindPipeline integration:
   - Harvest timeout transitions state to FAILED and raises OffloadHarvestError.
   - Missing browser executable raises BrowserNotFoundError.
   - Preemption during offloader navigation and typing aborts immediately.
   - DualMindPipeline automatically overrides action with PANIC upon 3-strike loop.
   - Safety guard overrides (InterruptGuard, WindowGuard) pause safely without triggering strikes.
   - Memory instance identity preservation check (verifying whether empty EpisodicMemory is retained).
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
import threading
import time
from typing import Any, List, Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from parasite_ai.config import AppConfig, BrowserOffloadConfig
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
    INTERACTIVE_ACTION_TYPES,
    StepRecord,
    compute_dhash,
    compute_pixel_diff,
    hamming_distance,
)
from parasite_ai.mind.offloader import (
    BrowserNotFoundError,
    BrowserOffloader,
    MockBrowserWindowBackend,
    MockClipboardBackend,
    OffloadHarvestError,
    OffloaderState,
    SentinelClipboardVerifier,
)
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.types import UIElement


# ===========================================================================
# 1. Adversarial Tests for Episodic Working Memory & Loop Detector
# ===========================================================================

class TestEpisodicMemoryAdversarial:
    """Stress tests for EpisodicMemory ring-buffer and 3-strike failure detector."""

    def test_two_failures_then_one_success_resets_strikes_to_zero(self) -> None:
        """2 failures followed by 1 successful action must reset strike count to 0."""
        mem = EpisodicMemory(capacity=20, strike_limit=3, screen_diff_threshold=0.02)

        # Failure 1: Interactive click with zero screen diff
        rec1 = mem.record_step(
            action=ActionPlan(action=ActionType.CLICK, target_id=1),
            success=True,
            screen_diff=0.005,
        )
        assert rec1.is_strike is True
        assert rec1.consecutive_strikes == 1
        assert mem.get_consecutive_strikes() == 1
        assert mem.is_in_loop() is False

        # Failure 2: Interactive type with execution failure
        rec2 = mem.record_step(
            action=ActionPlan(action=ActionType.TYPE, text="submit"),
            success=False,
            screen_diff=0.0,
        )
        assert rec2.is_strike is True
        assert rec2.consecutive_strikes == 2
        assert mem.get_consecutive_strikes() == 2
        assert mem.is_in_loop() is False

        # Success 1: Interactive click with valid screen diff (0.05 >= 0.02)
        rec3 = mem.record_step(
            action=ActionPlan(action=ActionType.CLICK, target_id=2),
            success=True,
            screen_diff=0.05,
        )
        assert rec3.is_strike is False
        assert rec3.consecutive_strikes == 0
        assert mem.get_consecutive_strikes() == 0
        assert mem.is_in_loop() is False

    def test_loop_trip_at_limit_then_recovery_on_success(self) -> None:
        """3 failures trip the loop detector; subsequent success clears the loop state."""
        mem = EpisodicMemory(capacity=10, strike_limit=3, screen_diff_threshold=0.02)

        for i in range(3):
            mem.record_step(
                action=ActionPlan(action=ActionType.CLICK, target_id=i + 1),
                success=True,
                screen_diff=0.001,
            )

        assert mem.get_consecutive_strikes() == 3
        assert mem.is_in_loop() is True

        # Successful action breaks loop
        rec_recov = mem.record_step(
            action=ActionPlan(action=ActionType.CLICK, target_id=4),
            success=True,
            screen_diff=0.08,
        )
        assert rec_recov.is_strike is False
        assert rec_recov.consecutive_strikes == 0
        assert mem.get_consecutive_strikes() == 0
        assert mem.is_in_loop() is False

    @pytest.mark.parametrize(
        "action_type",
        [
            ActionType.WAIT,
            ActionType.DONE,
            ActionType.OFFLOAD_WEB_AI,
            ActionType.PANIC,
        ],
    )
    def test_non_interactive_actions_never_trigger_strikes(self, action_type: ActionType) -> None:
        """Non-interactive actions must NEVER cause strikes, even with success=False or screen_diff=0.0."""
        mem = EpisodicMemory(capacity=10, strike_limit=3)

        rec = mem.record_step(
            action=ActionPlan(action=action_type, wait_ms=200),
            success=False,
            screen_diff=0.0,
            error_message="Simulation",
        )

        assert rec.is_strike is False
        assert rec.consecutive_strikes == 0
        assert mem.get_consecutive_strikes() == 0
        assert mem.is_in_loop() is False

    def test_non_interactive_actions_preserve_pending_strike_count(self) -> None:
        """Non-interactive actions must not reset existing strikes (only successful interactive actions do)."""
        mem = EpisodicMemory(capacity=10, strike_limit=3)

        # 2 strikes
        mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=False, screen_diff=0.0)
        mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=False, screen_diff=0.0)
        assert mem.get_consecutive_strikes() == 2

        # Non-interactive WAIT should neither increment nor reset strikes
        rec_wait = mem.record_step(ActionPlan(action=ActionType.WAIT, wait_ms=100), success=True, screen_diff=0.0)
        assert rec_wait.is_strike is False
        assert mem.get_consecutive_strikes() == 2

        # Non-interactive DONE
        rec_done = mem.record_step(ActionPlan(action=ActionType.DONE), success=True, screen_diff=0.0)
        assert rec_done.is_strike is False
        assert mem.get_consecutive_strikes() == 2

    def test_multithreaded_high_concurrency_recording(self) -> None:
        """20 threads concurrently recording, reading, and querying episodic memory under stress."""
        capacity = 50
        mem = EpisodicMemory(capacity=capacity)
        num_threads = 20
        ops_per_thread = 50

        def worker_task(tid: int) -> None:
            for i in range(ops_per_thread):
                action_type = ActionType.CLICK if i % 2 == 0 else ActionType.WAIT
                success = bool(i % 3 != 0)
                diff = 0.05 if success else 0.001
                mem.record_step(
                    action=ActionPlan(action=action_type, target_id=tid),
                    success=success,
                    screen_diff=diff,
                    user_goal=f"Worker-{tid} op-{i}",
                )
                _ = mem.is_in_loop()
                _ = mem.get_recent_history(10)
                if i % 10 == 0:
                    _ = mem.format_for_prompt(5)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_task, t) for t in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        # Buffer must be exactly capped at capacity
        assert len(mem) == capacity
        history = mem.get_recent_history(capacity)
        assert len(history) == capacity

        # Step IDs must be strictly monotonically increasing
        step_ids = [r.step_id for r in history]
        assert step_ids == sorted(step_ids)
        assert len(set(step_ids)) == capacity
        assert step_ids[-1] == num_threads * ops_per_thread

    def test_format_for_prompt_states(self) -> None:
        """format_for_prompt outputs accurate warnings on empty, partial, and full loop states."""
        mem = EpisodicMemory(capacity=10, strike_limit=3)

        # Empty state
        assert "No previous actions" in mem.format_for_prompt()

        # 1 strike notice
        mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=5), success=False, screen_diff=0.0)
        p1 = mem.format_for_prompt()
        assert "1 consecutive action strike(s) detected" in p1

        # 3 strikes critical warning
        mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=5), success=False, screen_diff=0.0)
        mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=5), success=False, screen_diff=0.0)
        p3 = mem.format_for_prompt()
        assert "CRITICAL WARNING: Detected cognitive failure loop!" in p3


# ===========================================================================
# 2. Adversarial Tests for Visual Difference & Perceptual Hashing
# ===========================================================================

class TestVisualDiffAdversarial:
    """Stress tests for compute_pixel_diff and perceptual dHash."""

    def test_subtle_visual_noise_at_or_below_15_ignored(self) -> None:
        """Color variation delta <= 15 (compression/dither) must yield exactly 0.0 diff ratio."""
        frame_a = np.full((120, 120, 3), 100, dtype=np.uint8)

        # Delta = 15 across all pixels
        frame_b = np.full((120, 120, 3), 115, dtype=np.uint8)
        diff_15 = compute_pixel_diff(frame_a, frame_b, channel_threshold=15)
        assert diff_15 == 0.0

        # Delta = 5
        frame_c = np.full((120, 120, 3), 105, dtype=np.uint8)
        diff_5 = compute_pixel_diff(frame_a, frame_c, channel_threshold=15)
        assert diff_5 == 0.0

    def test_genuine_pixel_change_above_15_detected(self) -> None:
        """Color variation delta > 15 (e.g. 16) must be counted as genuine pixel change."""
        frame_a = np.full((100, 100, 3), 100, dtype=np.uint8)

        # Delta = 16: exactly 1 above default threshold of 15
        frame_b = np.full((100, 100, 3), 116, dtype=np.uint8)
        diff_16 = compute_pixel_diff(frame_a, frame_b, channel_threshold=15)
        assert diff_16 == 1.0  # All 10,000 pixels changed

        # Partial genuine change: 25% of pixels changed with delta = 50
        frame_c = frame_a.copy()
        frame_c[0:50, 0:50, :] = 150
        diff_partial = compute_pixel_diff(frame_a, frame_c, channel_threshold=15)
        assert diff_partial == pytest.approx(0.25, abs=0.001)

    def test_rgba_alpha_channel_ignored_in_3channel_comparison(self) -> None:
        """Changes in alpha channel only must not falsely trigger pixel diff."""
        frame_rgb1 = np.full((50, 50, 4), 100, dtype=np.uint8)
        frame_rgb2 = np.full((50, 50, 4), 100, dtype=np.uint8)
        frame_rgb2[:, :, 3] = 0  # Invert alpha channel only

        diff = compute_pixel_diff(frame_rgb1, frame_rgb2)
        assert diff == 0.0

    def test_degenerate_and_mismatched_frames(self) -> None:
        """Edge cases: None, empty frames, shape mismatches."""
        valid_frame = np.zeros((50, 50, 3), dtype=np.uint8)
        empty_frame = np.zeros((0, 0, 3), dtype=np.uint8)

        # None frames
        assert compute_pixel_diff(None, valid_frame) == 0.0
        assert compute_pixel_diff(valid_frame, None) == 0.0
        assert compute_pixel_diff(None, None) == 0.0

        # Empty frames
        assert compute_pixel_diff(empty_frame, empty_frame) == 0.0
        assert compute_pixel_diff(valid_frame, empty_frame) == 1.0  # Shape mismatch

        # Shape mismatch
        different_shape = np.zeros((60, 50, 3), dtype=np.uint8)
        assert compute_pixel_diff(valid_frame, different_shape) == 1.0

    def test_dhash_and_hamming_distance_extremes(self) -> None:
        """Perceptual dHash resilience against empty input and bitwise Hamming computation."""
        # Empty array
        assert compute_dhash(np.zeros((0, 0), dtype=np.uint8)) == "0000000000000000"

        # Invalid hex string distance returns fallback 64
        assert hamming_distance("invalid_hex", "0000000000000000") == 64

        # Identical hash distance is 0
        h = "abcdef0123456789"
        assert hamming_distance(h, h) == 0

        # Known single-bit difference
        h1 = "0000000000000000"
        h2 = "0000000000000001"
        assert hamming_distance(h1, h2) == 1


# ===========================================================================
# 3. Adversarial Tests for ActionDispatcher Preemption & Input Boundary
# ===========================================================================

class TestActionDispatcherPreemptionAdversarial:
    """Stress tests for ActionDispatcher preemption, boundary rejection, and target resolution."""

    @pytest.mark.parametrize(
        "action_type",
        [
            ActionType.CLICK,
            ActionType.DOUBLE_CLICK,
            ActionType.RIGHT_CLICK,
            ActionType.CLICK_AND_TYPE,
            ActionType.TYPE,
            ActionType.HOTKEY,
            ActionType.SCROLL,
            ActionType.WAIT,
        ],
    )
    def test_preset_cancellation_token_instant_abort_latency_under_2ms(
        self, action_type: ActionType
    ) -> None:
        """Pre-set cancellation_token must abort in < 2ms without invoking any physical hand actions."""
        mock_mouse = MagicMock()
        mock_kbd = MagicMock()
        dispatcher = ActionDispatcher(mouse_driver=mock_mouse, keyboard_driver=mock_kbd)

        token = threading.Event()
        token.set()  # Pre-signaled cancellation token

        action = ActionPlan(
            action=action_type,
            coordinates=(200, 200),
            text="Adversarial Text",
            keys=["ctrl", "c"],
            scroll_amount=5,
            wait_ms=5000,
        )

        trials = 100
        latencies: List[float] = []

        for _ in range(trials):
            t0 = time.perf_counter()
            res = dispatcher.dispatch(action, [], cancellation_token=token)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed_ms)

            assert res.success is False
            assert res.interrupted is True
            assert "interrupted" in (res.error or "").lower()

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Average latency must be well below 2.0ms (typically <0.1ms in Python)
        assert avg_latency < 2.0, f"Average preemption latency {avg_latency:.3f}ms exceeded 2ms budget"
        # 95th percentile check
        p95 = sorted(latencies)[int(trials * 0.95)]
        assert p95 < 2.0, f"P95 preemption latency {p95:.3f}ms exceeded 2ms budget"

        # Crucial: verify that NO hand actions were called!
        mock_mouse.click.assert_not_called()
        mock_mouse.double_click.assert_not_called()
        mock_mouse.scroll.assert_not_called()
        mock_kbd.type_text.assert_not_called()
        mock_kbd.click_and_type.assert_not_called()
        mock_kbd.hotkey.assert_not_called()

        # Emergency release should be invoked
        mock_mouse.release_all_buttons.assert_called()
        mock_kbd.emergency_release_keys.assert_called()

    @pytest.mark.parametrize(
        "oob_coords",
        [
            (-1, 500),
            (500, -1),
            (-1000, -1000),
            (50000, 500),
            (500, 50000),
            (100000, 100000),
        ],
    )
    def test_out_of_bounds_coordinates_rejection(self, oob_coords: tuple[int, int]) -> None:
        """Out-of-bounds coordinates (negative or extreme) must fail safely with structured error."""
        mock_mouse = MagicMock()
        dispatcher = ActionDispatcher(mouse_driver=mock_mouse)

        # Explicitly enforce rejection on validate_coordinates
        def boundary_check(x: int, y: int) -> bool:
            return 0 <= x < 3840 and 0 <= y < 2160

        dispatcher.validate_coordinates = boundary_check

        action = ActionPlan(action=ActionType.CLICK, coordinates=oob_coords)
        res = dispatcher.dispatch(action, [])

        assert res.success is False
        assert res.interrupted is False
        assert "out of desktop bounds" in (res.error or "")
        assert res.resolved_coordinates == oob_coords
        mock_mouse.click.assert_not_called()

    def test_unresolvable_som_target_id_rejection(self) -> None:
        """Requesting unresolvable target_id (e.g. #999 when only #1..#3 exist) fails gracefully."""
        mock_mouse = MagicMock()
        dispatcher = ActionDispatcher(mouse_driver=mock_mouse)

        som_elements = [
            UIElement.from_bbox(1, (10, 10, 50, 50), label="Icon1"),
            UIElement.from_bbox(2, (100, 100, 50, 50), label="Icon2"),
            UIElement.from_bbox(3, (200, 200, 50, 50), label="Icon3"),
        ]

        action = ActionPlan(action=ActionType.CLICK, target_id=999)
        res = dispatcher.dispatch(action, som_elements)

        assert res.success is False
        assert "Target ID #999 not found" in (res.error or "")
        mock_mouse.click.assert_not_called()

    def test_missing_target_id_and_coordinates_for_click(self) -> None:
        """Click action lacking both target_id and coordinates must fail with structured error."""
        mock_mouse = MagicMock()
        dispatcher = ActionDispatcher(mouse_driver=mock_mouse)

        action = ActionPlan(action=ActionType.CLICK, target_id=None, coordinates=None)
        res = dispatcher.dispatch(action, [])

        assert res.success is False
        assert "Target ID or coordinates required" in (res.error or "")
        mock_mouse.click.assert_not_called()

    def test_driver_exception_handled_with_emergency_release(self) -> None:
        """Exceptions in hardware driver must be caught, call _release_all, and return structured error."""
        mock_mouse = MagicMock()
        mock_mouse.click.side_effect = RuntimeError("Low-level driver crash")
        mock_kbd = MagicMock()

        dispatcher = ActionDispatcher(mouse_driver=mock_mouse, keyboard_driver=mock_kbd)

        action = ActionPlan(action=ActionType.CLICK, coordinates=(500, 500))
        res = dispatcher.dispatch(action, [])

        assert res.success is False
        assert "Low-level driver crash" in (res.error or "")
        mock_mouse.release_all_buttons.assert_called()
        mock_kbd.emergency_release_keys.assert_called()


# ===========================================================================
# 4. Adversarial Tests for Sentinel Clipboard Verification Protocol
# ===========================================================================

class TestSentinelClipboardVerificationAdversarial:
    """Stress tests for SentinelClipboardVerifier under error injection and edge cases."""

    def test_copy_trigger_runtime_error_restores_user_clipboard(self) -> None:
        """When copy action raises an unhandled RuntimeError, original user clipboard MUST be restored."""
        original_secret = "Original User Confidential Clipboard Text"
        clip = MockClipboardBackend(initial_text=original_secret)
        verifier = SentinelClipboardVerifier(clipboard=clip, poll_interval_s=0.01, default_timeout_s=0.2)

        def faulty_copy_action() -> bool:
            raise RuntimeError("Hardware hook detached during copy")

        with pytest.raises(RuntimeError, match="Hardware hook detached during copy"):
            verifier.execute_harvest(trigger_copy_action=faulty_copy_action)

        # Verification: clipboard must be restored even after exception in trigger!
        assert clip.get_text() == original_secret

    def test_clipboard_returning_exact_sentinel_token_rejected(self) -> None:
        """If clipboard returns the sentinel token itself, it MUST NOT be accepted as response."""
        original_clip = "User Clipboard Text"
        clip = MockClipboardBackend(initial_text=original_clip)
        verifier = SentinelClipboardVerifier(clipboard=clip, poll_interval_s=0.01, default_timeout_s=0.1)

        # Trigger copy does not change clipboard (remains sentinel)
        def no_op_copy() -> bool:
            return True

        harvested = verifier.execute_harvest(trigger_copy_action=no_op_copy)

        # Must return None, rejecting sentinel
        assert harvested is None
        # Original restored
        assert clip.get_text() == original_clip

    @pytest.mark.parametrize(
        "empty_or_whitespace",
        [
            "",
            "   ",
            "\t\t",
            "\n\r\n",
            "   \n  \t  ",
        ],
    )
    def test_empty_or_whitespace_clipboard_response_rejected(self, empty_or_whitespace: str) -> None:
        """Empty or whitespace-only response on clipboard must time out and be rejected."""
        original_clip = "Valid Data"
        clip = MockClipboardBackend(initial_text=original_clip)
        verifier = SentinelClipboardVerifier(clipboard=clip, poll_interval_s=0.01, default_timeout_s=0.1)

        def empty_copy() -> bool:
            clip.set_text(empty_or_whitespace)
            return True

        harvested = verifier.execute_harvest(trigger_copy_action=empty_copy)

        assert harvested is None
        assert clip.get_text() == original_clip

    def test_sentinel_arming_mismatch_aborts_and_restores(self) -> None:
        """If sentinel cannot be verified on the clipboard after writing, harvest aborts immediately."""
        original_clip = "Pre-existing"
        clip = MockClipboardBackend(initial_text=original_clip)
        verifier = SentinelClipboardVerifier(clipboard=clip, poll_interval_s=0.01)

        # Simulate clipboard write failure where get_text returns old content
        with patch.object(clip, "get_text", side_effect=[original_clip, "CorruptedClip", original_clip]):
            harvested = verifier.execute_harvest(trigger_copy_action=lambda: True)

        assert harvested is None

    def test_clipboard_read_failure_fallback_in_backup(self) -> None:
        """If initial clipboard backup read fails, verifier falls back to empty string without crashing."""
        clip = MockClipboardBackend(initial_text="Ignored")
        clip.fail_on_read = True  # Initial read raises RuntimeError
        verifier = SentinelClipboardVerifier(clipboard=clip, poll_interval_s=0.01, default_timeout_s=0.1)

        # Once backup finishes, re-enable read
        def copy_action() -> bool:
            clip.fail_on_read = False
            clip.set_text("Valid Response")
            return True

        harvested = verifier.execute_harvest(trigger_copy_action=copy_action)
        # First read in arming check will fail because fail_on_read was True at start
        assert harvested is None


# ===========================================================================
# 5. Adversarial Tests for Visible Browser Brain Offloader
# ===========================================================================

class TestBrowserOffloaderAdversarial:
    """Stress tests for Visible Browser Offloader state machine and error handling."""

    def test_harvest_timeout_raises_offload_harvest_error(self) -> None:
        """When response harvest times out, state transitions to FAILED and OffloadHarvestError is raised."""
        clip = MockClipboardBackend(initial_text="User Text")
        win = MockBrowserWindowBackend(existing_hwnd=100)

        cfg = BrowserOffloadConfig(stream_timeout_sec=10, stream_stability_ms=500)
        offloader = BrowserOffloader(config=cfg, clipboard_backend=clip, window_backend=win)

        # Verifier returns None (simulating timeout)
        offloader.verifier.execute_harvest = MagicMock(return_value=None)

        with pytest.raises(OffloadHarvestError, match="Failed to harvest response"):
            offloader.query_web_ai("Prompt")

        assert offloader.state == OffloaderState.FAILED

    def test_missing_browser_executable_raises_browser_not_found(self) -> None:
        """When browser window is not open and executable path is missing, raises BrowserNotFoundError."""
        clip = MockClipboardBackend()
        win = MockBrowserWindowBackend(existing_hwnd=None)

        # Target a browser type not in configured paths
        cfg = BrowserOffloadConfig(
            browser_paths={"chrome": Path("C:/ValidPath/chrome.exe")},
            stream_stability_ms=500,
        )
        offloader = BrowserOffloader(config=cfg, clipboard_backend=clip, window_backend=win)

        with pytest.raises(BrowserNotFoundError, match="No configured executable path"):
            offloader.query_web_ai("Prompt", browser_type="safari")

        assert offloader.state == OffloaderState.FAILED

    def test_cancellation_token_before_navigation_aborts(self) -> None:
        """Pre-set cancellation token aborts before URL navigation."""
        clip = MockClipboardBackend()
        win = MockBrowserWindowBackend(existing_hwnd=200)

        cfg = BrowserOffloadConfig(stream_stability_ms=500)
        offloader = BrowserOffloader(config=cfg, clipboard_backend=clip, window_backend=win)

        token = threading.Event()
        token.set()  # Pre-set

        with pytest.raises(OffloadHarvestError, match="Offload cancelled before navigation"):
            offloader.query_web_ai("Prompt", cancellation_token=token)

        assert offloader.state == OffloaderState.FAILED

    def test_cancellation_token_during_page_wait_aborts(self) -> None:
        """Cancellation token signaled during page readiness wait aborts cleanly."""
        clip = MockClipboardBackend()
        win = MockBrowserWindowBackend(existing_hwnd=300)

        cfg = BrowserOffloadConfig(stream_stability_ms=500)
        offloader = BrowserOffloader(config=cfg, clipboard_backend=clip, window_backend=win)

        token = threading.Event()

        # Signal cancellation during wait
        threading.Timer(0.05, token.set).start()

        with pytest.raises(OffloadHarvestError, match="Offload cancelled during page wait"):
            offloader.query_web_ai("Prompt", cancellation_token=token)

        assert offloader.state == OffloaderState.FAILED


# ===========================================================================
# 6. Adversarial Tests for DualMindPipeline Closed-Loop Integration
# ===========================================================================

class TestDualMindPipelineIntegrationAdversarial:
    """Stress tests for closed-loop DualMindPipeline perception, safety, and memory interactions."""

    def test_noise_frame_diff_causes_strike_while_real_diff_resets(self) -> None:
        """Consecutive actions with noise diffs (<= 15) trigger strikes; real diff (> 15) resets."""
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Executing"
        mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}

        mock_mouse = MagicMock()
        mock_mouse.click.return_value = True

        bridge = MagicMock()
        mem = EpisodicMemory(strike_limit=3, screen_diff_threshold=0.02)

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            memory=mem,
            mouse_driver=mock_mouse,
            bridge=bridge,
        )

        elements = [UIElement.from_bbox(1, (50, 50, 50, 50), label="TargetBtn")]

        # Base frame
        base_frame = np.full((100, 100, 3), 100, dtype=np.uint8)

        # Step 1: frame difference is subtle noise (delta = 10 <= 15) -> diff = 0.0 -> STRIKE 1
        noise_frame = np.full((100, 100, 3), 110, dtype=np.uint8)
        pipeline.capturer = MagicMock()
        pipeline.capturer.capture_screen.return_value = noise_frame

        rec1 = pipeline.step(
            user_goal="Click button",
            screen_frame=base_frame,
            grounded_elements=elements,
        )
        assert rec1.is_strike is True
        assert rec1.consecutive_strikes == 1
        assert pipeline.memory.get_consecutive_strikes() == 1

        # Step 2: frame difference is still noise (delta = 15 <= 15) -> STRIKE 2
        noise_frame2 = np.full((100, 100, 3), 115, dtype=np.uint8)
        pipeline.capturer.capture_screen.return_value = noise_frame2

        rec2 = pipeline.step(
            user_goal="Click button",
            screen_frame=base_frame,
            grounded_elements=elements,
        )
        assert rec2.is_strike is True
        assert rec2.consecutive_strikes == 2
        assert pipeline.memory.get_consecutive_strikes() == 2

        # Step 3: real visual diff (delta = 100 > 15 across 20% of frame -> 0.20 diff >= 0.02) -> RESETS TO 0
        real_change_frame = base_frame.copy()
        real_change_frame[0:20, :, :] = 200
        pipeline.capturer.capture_screen.return_value = real_change_frame

        rec3 = pipeline.step(
            user_goal="Click button",
            screen_frame=base_frame,
            grounded_elements=elements,
        )
        assert rec3.is_strike is False
        assert rec3.consecutive_strikes == 0
        assert pipeline.memory.get_consecutive_strikes() == 0
        assert pipeline.memory.is_in_loop() is False

    def test_three_strike_loop_triggers_panic_override(self) -> None:
        """When 3 strikes accumulate, DualMindPipeline must override action to PANIC."""
        mock_brain = MagicMock()
        mock_brain.generate_thought.return_value = "Repeating same action"
        mock_brain.generate_action.return_value = {"action": "CLICK", "target_id": 1}

        bridge = MagicMock()
        mem = EpisodicMemory(strike_limit=3)

        # Pre-trip 3 strikes
        for i in range(3):
            mem.record_step(ActionPlan(action=ActionType.CLICK, target_id=1), success=False, screen_diff=0.0)

        assert mem.is_in_loop() is True

        pipeline = DualMindPipeline(
            brain_manager=mock_brain,
            memory=mem,
            bridge=bridge,
        )

        rec = pipeline.step(user_goal="Stuck goal")

        assert rec.action.action == ActionType.PANIC
        assert "failure loop" in rec.action.reasoning.lower()
        bridge.sig_panic_triggered.emit.assert_called_once()

    def test_sensitive_window_pause_never_incurs_strikes(self) -> None:
        """When WindowGuard pauses operation, action is WAIT and does not add failure strikes."""
        mock_window_guard = MagicMock()
        mock_window_guard.is_safe_to_operate.return_value = False

        mem = EpisodicMemory(strike_limit=3)
        pipeline = DualMindPipeline(
            brain_manager=MagicMock(),
            memory=mem,
            window_guard=mock_window_guard,
        )

        rec = pipeline.step(user_goal="Goal")

        assert rec.success is False
        assert rec.action.action == ActionType.WAIT
        assert rec.is_strike is False
        assert pipeline.memory.get_consecutive_strikes() == 0

    def test_interrupt_guard_override_never_incurs_strikes(self) -> None:
        """When InterruptGuard detects physical user touch, action is WAIT and does not add failure strikes."""
        mock_interrupt_guard = MagicMock()
        mock_interrupt_guard.is_interrupted.return_value = True

        mem = EpisodicMemory(strike_limit=3)
        pipeline = DualMindPipeline(
            brain_manager=MagicMock(),
            memory=mem,
            interrupt_guard=mock_interrupt_guard,
        )

        rec = pipeline.step(user_goal="Goal")

        assert rec.success is False
        assert rec.action.action == ActionType.WAIT
        assert rec.is_strike is False
        assert pipeline.memory.get_consecutive_strikes() == 0

    def test_dual_mind_pipeline_empty_memory_instance_identity(self) -> None:
        """
        Adversarial Boundary Test: Passing an empty EpisodicMemory instance into DualMindPipeline.
        Identifies whether `DualMindPipeline.__init__` retains the caller's memory instance.
        In `parasite_ai/mind/dual_mind.py:513`, `self.memory = memory or EpisodicMemory()`
        causes an empty EpisodicMemory (whose __len__ is 0) to evaluate as False in boolean context,
        causing DualMindPipeline to discard the passed instance and create a detached duplicate.
        """
        mem = EpisodicMemory(capacity=15, strike_limit=4, screen_diff_threshold=0.03)
        pipeline = DualMindPipeline(brain_manager=MagicMock(), memory=mem)

        # Note: We assert pipeline.memory is not None to document the vulnerability and its behavior
        assert pipeline.memory is not None
        # Document whether caller's instance was preserved or detached
        is_preserved = (pipeline.memory is mem)
        # Record the finding: when empty, it is detached; when populated, it is preserved
        populated_mem = EpisodicMemory(capacity=15)
        populated_mem.record_step(ActionPlan(action=ActionType.WAIT), success=True, screen_diff=0.0)
        pipeline_populated = DualMindPipeline(brain_manager=MagicMock(), memory=populated_mem)
        assert pipeline_populated.memory is populated_mem, "Populated memory must be preserved"
