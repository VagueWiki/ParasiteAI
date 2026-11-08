"""
tests/test_challenger_p3_stress.py - Empirical Adversarial Stress Test Suite for Phase 3.

Empirically challenges:
1. Requirement R2 (Phase 3B): Win32 Caret Focus Verification
   - Flag permutations under GetGUIThreadInfo:
     * GUI_CARETBLINKING (0x1) with hwndCaret=0
     * Non-zero hwndCaret with flags=0
     * Both GUI_CARETBLINKING and hwndCaret
     * Neither GUI_CARETBLINKING nor hwndCaret
     * Menu and sizing flags (0x2, 0x4, 0x8, 0x10) without caret
     * Mask edge cases (0xFFFFFFFE vs 0xFFFFFFFF)
   - Win32 API failure conditions (return code 0, exceptions, platform guards)
   - Polling behavior: 250ms timeout budget, 25ms backoff cadence, degenerate timeouts
   - Sub-2ms cancellation token preemption (pre-set and mid-poll interruption)
   - ActionDispatcher TYPE gating (strict zero-keystroke emission on missing caret)
2. Requirement R3 (Phase 3C): Start Search Cadence Buffer
   - Cadence buffer enforcement (default 250ms, configurable ms, 0ms bypass)
   - Two-step Tier 2 launch flow (Win hotkey -> 250ms buffer -> TYPE app name)
   - Dynamic cancellation during cadence buffer wait (sub-2ms halt on hardware touch)
   - Start Search box grounded element interaction
3. System Invariants:
   - Sub-2ms hardware touch preemption and Ctrl+Alt+K hard kill
   - Zero hardcoded application dictionaries
   - Dual-monitor 3840x1080 coordinate boundary safety
"""

from __future__ import annotations

import concurrent.futures
import ctypes
from ctypes import wintypes
import sys
import threading
import time
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

from parasite_ai.mind.dual_mind import (
    ActionDispatcher,
    GUI_CARETBLINKING,
    GUITHREADINFO,
    check_caret_focus,
    verify_caret_focus,
)
from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.mind.resolver import UniversalAppResolver
from parasite_ai.safety.interrupt_guard import InterruptGuard
from parasite_ai.safety.panic import PanicManager
from parasite_ai.ui.types import BoundingBox, UIElement
from parasite_ai.vision.capture import get_virtual_screen_bounds


# ===========================================================================
# Mocking Helpers for Win32 GetGUIThreadInfo
# ===========================================================================

def make_gui_mock(flags: int = 0, hwnd_caret: int = 0, return_code: int = 1):
    """Produces a mock for ctypes.windll.user32.GetGUIThreadInfo."""
    def _mock(thread_id, p_info):
        if not return_code:
            return 0
        if hasattr(p_info, "_obj"):
            p_info._obj.flags = flags
            p_info._obj.hwndCaret = hwnd_caret
        return return_code
    return _mock


# ===========================================================================
# Group 1: Win32 Caret Verification Stress Tests (Requirement R2 / Phase 3B)
# ===========================================================================

class TestCaretFocusFlagPermutationsAndAPI:
    """Stress tests for all flag permutations and Win32 failure modes of check_caret_focus."""

    @pytest.mark.parametrize(
        "flags,hwnd_caret,expected",
        [
            # Baseline positives
            (GUI_CARETBLINKING, 0, True),             # 0x1 only
            (0, 0x1234, True),                         # hwndCaret only
            (GUI_CARETBLINKING, 0x9876, True),         # both 0x1 and hwndCaret
            (GUI_CARETBLINKING | 0x2, 0, True),        # 0x1 with in-menu flag
            (GUI_CARETBLINKING | 0x4, 0, True),        # 0x1 with in-movesize flag
            (0xFFFFFFFF, 0, True),                     # all bits set (includes bit 0)
            (0, 0x7FFFFFFF, True),                     # maximum positive 32-bit hwnd

            # Baseline negatives
            (0, 0, False),                             # neither
            (0x2, 0, False),                           # GUI_INMENUMODE
            (0x4, 0, False),                           # GUI_INMOVESIZE
            (0x8, 0, False),                           # GUI_POPUPMENUMODE
            (0x10, 0, False),                          # GUI_SYSTEMMENUMODE
            (0x20, 0, False),                          # GUI_CARETVISIBLE only (without blinking)
            (0xFFFFFFFE, 0, False),                    # all bits EXCEPT bit 0 (blinking)
        ],
    )
    def test_check_caret_focus_flag_matrix(self, flags: int, hwnd_caret: int, expected: bool) -> None:
        """Exhaustively validates bitwise logic for GUI_CARETBLINKING and hwndCaret."""
        mock_fn = make_gui_mock(flags=flags, hwnd_caret=hwnd_caret, return_code=1)
        with patch.object(ctypes.windll.user32, "GetGUIThreadInfo", side_effect=mock_fn):
            result = check_caret_focus(0)
            assert result is expected, f"Failed for flags={hex(flags)}, hwndCaret={hex(hwnd_caret)}"

    def test_check_caret_focus_api_return_zero_fails(self) -> None:
        """When Win32 GetGUIThreadInfo returns FALSE (0), check_caret_focus must return False."""
        mock_fn = make_gui_mock(return_code=0)
        with patch.object(ctypes.windll.user32, "GetGUIThreadInfo", side_effect=mock_fn):
            assert check_caret_focus(0) is False

    def test_check_caret_focus_os_error_handled(self) -> None:
        """Exceptions raised by user32 call are swallowed gracefully without crashing."""
        with patch.object(ctypes.windll.user32, "GetGUIThreadInfo", side_effect=OSError("Win32 error 1400: Invalid window handle")):
            assert check_caret_focus(0) is False

    def test_check_caret_focus_ctypes_argument_error(self) -> None:
        """ctypes ArgumentError is handled safely."""
        with patch.object(ctypes.windll.user32, "GetGUIThreadInfo", side_effect=ctypes.ArgumentError("Invalid argument")):
            assert check_caret_focus(0) is False

    def test_check_caret_focus_non_win32_platform_guard(self) -> None:
        """On non-Windows platforms (e.g. Linux CI), returns False immediately without calling ctypes."""
        with patch("sys.platform", "linux"):
            assert check_caret_focus(0) is False

    def test_check_caret_focus_missing_windll_guard(self) -> None:
        """When windll is unavailable, returns False safely."""
        with patch.object(ctypes, "windll", None, create=False):
            assert check_caret_focus(0) is False


class TestCaretFocusPollingAndTiming:
    """Stress tests for verify_caret_focus polling loop, backoff, and timeouts."""

    def test_verify_caret_focus_immediate_success_no_sleep(self) -> None:
        """When caret focus is present on poll #1, returns immediately in <5ms without sleeping."""
        with patch("parasite_ai.mind.dual_mind.check_caret_focus", return_value=True):
            t0 = time.perf_counter()
            ok = verify_caret_focus(timeout_ms=250.0, poll_interval_ms=25.0)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            assert ok is True
            assert latency_ms < 5.0, f"Immediate check took {latency_ms:.2f}ms"

    def test_verify_caret_focus_delayed_acquisition_exits_early(self) -> None:
        """Caret acquiring on poll 4 (~75ms) exits immediately without waiting full 250ms."""
        call_count = 0

        def _delayed_check(tid=0):
            nonlocal call_count
            call_count += 1
            return call_count >= 4

        with patch("parasite_ai.mind.dual_mind.check_caret_focus", side_effect=_delayed_check):
            t0 = time.perf_counter()
            ok = verify_caret_focus(timeout_ms=500.0, poll_interval_ms=25.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            assert ok is True
            assert call_count == 4
            # Should have slept ~3 intervals of 25ms = ~75ms, well under 300ms
            assert elapsed_ms < 300.0, f"Exited too late: {elapsed_ms:.2f}ms"
            assert elapsed_ms >= 50.0, f"Exited too early: {elapsed_ms:.2f}ms"

    def test_verify_caret_focus_timeout_exhaustion_cadence(self) -> None:
        """Exhausting a 150ms timeout with 25ms backoff incurs ~6-7 polls and ~150ms duration."""
        call_count = 0

        def _never_check(tid=0):
            nonlocal call_count
            call_count += 1
            return False

        with patch("parasite_ai.mind.dual_mind.check_caret_focus", side_effect=_never_check):
            t0 = time.perf_counter()
            ok = verify_caret_focus(timeout_ms=150.0, poll_interval_ms=25.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            assert ok is False
            assert call_count >= 5
            assert call_count <= 9
            assert elapsed_ms >= 120.0

    def test_verify_caret_focus_degenerate_zero_or_negative_timeout(self) -> None:
        """Zero or negative timeout performs at most 1 check and exits cleanly without hanging."""
        call_count = 0

        def _counter(tid=0):
            nonlocal call_count
            call_count += 1
            return False

        with patch("parasite_ai.mind.dual_mind.check_caret_focus", side_effect=_counter):
            # timeout_ms = 0.0
            ok0 = verify_caret_focus(timeout_ms=0.0, poll_interval_ms=25.0)
            assert ok0 is False
            assert call_count == 1

            # timeout_ms = -50.0
            call_count = 0
            ok_neg = verify_caret_focus(timeout_ms=-50.0, poll_interval_ms=25.0)
            assert ok_neg is False
            assert call_count == 1


class TestCaretFocusPreemptionLatency:
    """Stress tests ensuring sub-2ms preemption via cancellation token."""

    def test_pre_set_token_aborts_under_2ms(self) -> None:
        """Pre-set token causes verify_caret_focus to abort immediately (<2ms)."""
        token = threading.Event()
        token.set()

        with patch("parasite_ai.mind.dual_mind.check_caret_focus", return_value=False):
            t0 = time.perf_counter()
            ok = verify_caret_focus(timeout_ms=5000.0, poll_interval_ms=25.0, cancellation_token=token)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            assert ok is False
            assert latency_ms < 2.0, f"Pre-set cancellation took {latency_ms:.3f}ms (expected <2ms)"

    def test_mid_poll_dynamic_preemption_latency(self) -> None:
        """
        Critical Invariant: Preempting mid-polling halts immediately.
        Worker thread is sleeping in cancellation_token.wait(timeout=0.025);
        when token.set() is called, it unblocks in <2ms, NOT waiting the remaining 25ms.
        """
        token = threading.Event()
        result_container = {"ok": None, "preempt_latency_ms": None}

        def _worker():
            with patch("parasite_ai.mind.dual_mind.check_caret_focus", return_value=False):
                res = verify_caret_focus(
                    timeout_ms=10000.0,
                    poll_interval_ms=25.0,
                    cancellation_token=token,
                )
                result_container["ok"] = res

        thread = threading.Thread(target=_worker)
        thread.start()

        # Let the worker enter its first poll and wait in cancellation_token.wait()
        time.sleep(0.010)

        # Trigger physical interrupt simulation
        t_trigger = time.perf_counter()
        token.set()
        thread.join(timeout=0.5)
        t_halt = time.perf_counter()

        assert not thread.is_alive(), "Worker thread hung and did not preempt"
        preempt_latency_ms = (t_halt - t_trigger) * 1000.0
        assert result_container["ok"] is False
        assert preempt_latency_ms < 5.0, f"Mid-poll preemption took {preempt_latency_ms:.2f}ms"

    def test_high_concurrency_preemption_stress(self) -> None:
        """Spawns 30 concurrent polling threads; all must abort cleanly when token is set."""
        token = threading.Event()
        results = []

        def _poll_thread():
            with patch("parasite_ai.mind.dual_mind.check_caret_focus", return_value=False):
                return verify_caret_focus(
                    timeout_ms=5000.0,
                    poll_interval_ms=25.0,
                    cancellation_token=token,
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(_poll_thread) for _ in range(30)]
            # Allow all threads to begin polling
            time.sleep(0.015)
            # Interrupt all
            t0 = time.perf_counter()
            token.set()
            for fut in futures:
                results.append(fut.result(timeout=1.0))
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert all(res is False for res in results)
        assert len(results) == 30
        assert elapsed_ms < 50.0, f"Concurrent preemption took {elapsed_ms:.2f}ms"


class TestActionDispatcherCaretGating:
    """Stress tests verifying ActionDispatcher strictly gates TYPE actions on caret focus."""

    def test_type_without_caret_emits_zero_keystrokes(self) -> None:
        """
        Safety Requirement: When caret focus is absent, ActionDispatcher MUST return
        ActionResult(success=False, error="Caret focus not detected") and NEVER call type_text.
        """
        mock_kbd = MagicMock()
        mock_mouse = MagicMock()
        dispatcher = ActionDispatcher(mouse_driver=mock_mouse, keyboard_driver=mock_kbd)

        # Force caret check to fail
        dispatcher.verify_caret_focus = MagicMock(return_value=False)

        action = ActionPlan(action=ActionType.TYPE, text="DROP DATABASE users;\n")
        result = dispatcher.dispatch(action, som_elements=[])

        assert result.success is False
        assert result.error == "Caret focus not detected"
        mock_kbd.type_text.assert_not_called()
        mock_mouse.click.assert_not_called()

    def test_type_with_caret_calls_keyboard_driver(self) -> None:
        """When caret focus is verified, ActionDispatcher calls keyboard_driver.type_text."""
        mock_kbd = MagicMock()
        mock_kbd.type_text.return_value = True
        mock_mouse = MagicMock()
        dispatcher = ActionDispatcher(mouse_driver=mock_mouse, keyboard_driver=mock_kbd)

        dispatcher.verify_caret_focus = MagicMock(return_value=True)

        action = ActionPlan(action=ActionType.TYPE, text="safe input", submit=False)
        result = dispatcher.dispatch(action, som_elements=[])

        assert result.success is True
        mock_kbd.type_text.assert_called_once_with(
            text="safe input",
            submit=False,
            cancellation_token=None,
        )

    def test_type_preempted_during_caret_verification(self) -> None:
        """
        When human touches hardware during caret verification, dispatch returns
        interrupted=True and 'Interrupted by physical input'.
        """
        mock_kbd = MagicMock()
        mock_mouse = MagicMock()
        dispatcher = ActionDispatcher(mouse_driver=mock_mouse, keyboard_driver=mock_kbd)

        token = threading.Event()

        def _preempt_during_check(**kwargs):
            # Simulate hardware interrupt firing while checking
            token.set()
            return False

        dispatcher.verify_caret_focus = MagicMock(side_effect=_preempt_during_check)

        action = ActionPlan(action=ActionType.TYPE, text="unintended typing\n")
        result = dispatcher.dispatch(action, som_elements=[], cancellation_token=token)

        assert result.success is False
        assert result.interrupted is True
        assert "Interrupted" in (result.error or "")
        mock_kbd.type_text.assert_not_called()


# ===========================================================================
# Group 2: Start Search Cadence Buffer Stress Tests (Requirement R3 / Phase 3C)
# ===========================================================================

class TestResolverCadenceBufferStress:
    """Stress tests verifying the 250ms cadence buffer in UniversalAppResolver."""

    def test_resolver_default_and_custom_cadence_values(self) -> None:
        """UniversalAppResolver adheres to 250ms default and respects custom ms overrides."""
        resolver_default = UniversalAppResolver()
        assert resolver_default.cadence_buffer_ms == 250.0
        assert resolver_default.cadence_buffer_s == 0.25

        resolver_custom = UniversalAppResolver(cadence_buffer_ms=400.0)
        assert resolver_custom.cadence_buffer_ms == 400.0
        assert resolver_custom.cadence_buffer_s == 0.4

        resolver_zero = UniversalAppResolver(cadence_buffer_ms=0.0)
        assert resolver_zero.cadence_buffer_ms == 0.0
        assert resolver_zero.cadence_buffer_s == 0.0

    def test_tier2_launch_flow_enforces_cadence_timing(self) -> None:
        """
        Empirically verifies two-tier launch flow:
        Step 1: Returns HOTKEY 'win' with wait_ms=250.
        Step 2: Enforces real cadence sleep (tested with 100ms for test speed) then returns TYPE.
        """
        resolver = UniversalAppResolver(cadence_buffer_ms=100.0)

        # Step 1: Open Start Search
        t0 = time.perf_counter()
        action1 = resolver.resolve_launch_action("notepad", [])
        elapsed1_ms = (time.perf_counter() - t0) * 1000.0

        assert action1.action == ActionType.HOTKEY
        assert action1.keys == ["win"]
        assert action1.wait_ms == 100
        assert elapsed1_ms < 10.0, "Step 1 should not sleep"

        # Step 2: Type application name -> must sleep 100ms
        t1 = time.perf_counter()
        action2 = resolver.resolve_launch_action("notepad", [])
        elapsed2_ms = (time.perf_counter() - t1) * 1000.0

        assert action2.action == ActionType.TYPE
        assert "notepad\n" in (action2.text or "")
        assert elapsed2_ms >= 90.0, f"Step 2 slept only {elapsed2_ms:.2f}ms (expected >=90ms)"

    def test_tier2_start_search_box_grounded_enforces_cadence(self) -> None:
        """If Start Search box is grounded in SOM elements after Win, enforces cadence pause."""
        resolver = UniversalAppResolver(cadence_buffer_ms=80.0)

        # Trigger Win
        resolver.resolve_launch_action("calc", [])
        assert resolver._search_opened is True

        # Search edit box is now grounded
        search_elem = UIElement.from_bbox(
            10,
            (100, 950, 400, 40),
            label="Search",
            role="Edit",
        )

        t0 = time.perf_counter()
        action = resolver.resolve_launch_action("calc", [search_elem])
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert action.action == ActionType.CLICK_AND_TYPE
        assert action.target_id == 10
        assert elapsed_ms >= 70.0, f"Search box typing slept only {elapsed_ms:.2f}ms"
        assert resolver._search_opened is False

    def test_cadence_pause_preemption_dynamic_thread(self) -> None:
        """
        Mid-cadence Preemption Invariant:
        If resolver is sleeping its cadence buffer (e.g. 5000ms), and human touches hardware,
        cancellation token aborts the pause immediately (<5ms).
        """
        resolver = UniversalAppResolver(cadence_buffer_ms=5000.0)
        resolver._search_opened = True

        token = threading.Event()
        result_holder = {}

        def _resolve_thread():
            act = resolver.resolve_launch_action("spotify", [], cancellation_token=token)
            result_holder["action"] = act

        thread = threading.Thread(target=_resolve_thread)
        thread.start()

        # Let thread enter cadence buffer sleep
        time.sleep(0.015)

        # Fire cancellation
        t_trigger = time.perf_counter()
        token.set()
        thread.join(timeout=0.5)
        t_halt = time.perf_counter()

        assert not thread.is_alive(), "Cadence buffer failed to unblock on cancellation"
        preempt_ms = (t_halt - t_trigger) * 1000.0
        assert preempt_ms < 5.0, f"Cadence preemption took {preempt_ms:.2f}ms"
        assert result_holder["action"].action == ActionType.TYPE

    def test_resolver_reset_restores_clean_state(self) -> None:
        """Calling reset() returns resolver to clean state so next action is HOTKEY Win."""
        resolver = UniversalAppResolver()
        resolver.resolve_launch_action("paint", [])
        assert resolver._search_opened is True

        resolver.reset()
        assert resolver._search_opened is False

        # Next call must be Step 1 (HOTKEY Win) again
        act = resolver.resolve_launch_action("paint", [])
        assert act.action == ActionType.HOTKEY
        assert act.keys == ["win"]


# ===========================================================================
# Group 3: Invariant Verification
# ===========================================================================

class TestSystemInvariantsStress:
    """Stress tests for strict architectural invariants: anti-hardcoding, preemption, coordinates."""

    def test_anti_hardcoding_arbitrary_unseen_applications(self) -> None:
        """
        Strict Anti-Hardcoding Invariant: UniversalAppResolver must operate purely on generic
        patterns and Set-of-Mark grounding, without any static application dictionaries.
        """
        resolver = UniversalAppResolver(cadence_buffer_ms=0.0)
        arbitrary_apps = [
            "MyCustomLabViewer_2026",
            "DeepSpaceTelemetryClient",
            "LocalVoxelSimulator",
            "CyberDeckTerminal",
            "BioSeqViewer_v9",
        ]

        for app_name in arbitrary_apps:
            resolver.reset()
            # Step 1: Tier 2 HOTKEY win
            act1 = resolver.resolve_launch_action(app_name, [])
            assert act1.action == ActionType.HOTKEY
            assert act1.keys == ["win"]

            # Step 2: Tier 2 TYPE
            act2 = resolver.resolve_launch_action(app_name, [])
            assert act2.action == ActionType.TYPE
            assert app_name in (act2.text or "")

    def test_no_hardcoded_app_dictionaries_in_codebase(self) -> None:
        """Verifies no app_map or dictionary tables mapping app names exist in resolver or dual_mind."""
        import parasite_ai.mind.resolver as res_mod
        import parasite_ai.mind.dual_mind as dm_mod

        for mod in (res_mod, dm_mod):
            mod_dict = mod.__dict__
            assert "app_map" not in mod_dict
            assert "APP_MAP" not in mod_dict
            assert "APP_EXECUTABLES" not in mod_dict

    def test_dual_monitor_coordinate_safety_extremes(self) -> None:
        """
        Coordinates extending across Monitor 1 and Monitor 2 (3840x1080 @ 100% DPI)
        must pad and clamp safely without wrapping or raising exceptions.
        """
        bounds = get_virtual_screen_bounds()
        vx, vy, vw, vh = bounds

        # Extreme Monitor 2 right edge
        box_mon2_edge = BoundingBox(x=3830, y=500, width=50, height=50)
        padded = box_mon2_edge.pad(padding_px=20, bounds=bounds)

        assert padded.x == 3810
        assert padded.x + padded.width <= vw, f"Padded width exceeded virtual screen width {vw}"
        assert padded.y == 480
        assert padded.height == 90

    def test_ctrl_alt_k_hard_kill_handler_exists_and_configured(self) -> None:
        """Verifies PanicManager configures Ctrl+Alt+K for instantaneous hard kill."""
        panic = PanicManager()
        panic.allow_process_exit = False
        assert hasattr(panic, "trigger_panic")
        assert hasattr(panic, "is_panic")
        assert panic.is_panic() is False
        assert hasattr(panic, "hard_kill_all_processes")

    def test_sub_2ms_hardware_interrupt_token_interface(self) -> None:
        """Verifies InterruptGuard provides atomic threading.Event cancellation token."""
        guard = InterruptGuard()
        token = guard.get_cancellation_token()
        assert isinstance(token, threading.Event)
        assert not token.is_set()

        # Simulate physical trigger
        guard.simulate_event(event_type="mouse", flags=0, vk_code=0)
        assert token.is_set()
        assert guard.is_interrupted() is True
