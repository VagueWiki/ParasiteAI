"""
Tests for ParasiteAI Global Panic Abort Subsystem.
Verifies emergency panic triggers (Esc, Ctrl+Alt+P, Ctrl+Alt+Backspace, Screen Corner Slam),
synthetic input filtering, multi-callback notification, emergency hardware state neutralization,
and panic reset lifecycle.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from unittest.mock import MagicMock
import pytest

from parasite_ai.config import SafetyConfig
from parasite_ai.hands.keyboard import (
    INPUT_KEYBOARD,
    INPUT_MOUSE,
    KEYEVENTF_KEYUP,
    LLKHF_ALTDOWN,
    LLKHF_INJECTED,
    LLKHF_UP,
    LLMHF_INJECTED,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_MIDDLEUP,
    MOUSEEVENTF_RIGHTUP,
    VK_BACK,
    VK_CONTROL,
    VK_ESCAPE,
    VK_MENU,
    VK_P,
    VK_SHIFT,
    MockInputBackend,
)
from parasite_ai.safety.panic import PanicManager, PanicTriggerSource, VK_K, VK_Q


class TestPanicManagerKeyTriggers:
    """Verifies keyboard-based panic triggers and synthetic event filtering."""

    def test_esc_key_triggers_panic_when_driving_or_offloading(self):
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)

        # Esc in DRIVING state triggers panic
        assert panic.is_panic() is False
        fired = panic.check_key_event(VK_ESCAPE, flags=0, active_state="DRIVING")
        assert fired is True
        assert panic.is_panic() is True
        assert panic.get_panic_reason() == PanicTriggerSource.ESC_KEY
        assert panic.get_panic_event().is_set()

        # Reset and test OFFLOADING
        panic.reset_panic()
        assert panic.is_panic() is False
        fired = panic.check_key_event(VK_ESCAPE, flags=0, active_state="OFFLOADING")
        assert fired is True
        assert panic.is_panic() is True
        assert panic.get_panic_reason() == PanicTriggerSource.ESC_KEY

        # Reset and test ANY
        panic.reset_panic()
        fired = panic.check_key_event(VK_ESCAPE, flags=0, active_state="ANY")
        assert fired is True
        assert panic.is_panic() is True

    def test_esc_key_ignored_when_idle_or_watching(self):
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)

        # In WATCHING or THINKING state, Esc should NOT trigger panic
        for state in ("WATCHING", "THINKING", "IDLE"):
            fired = panic.check_key_event(VK_ESCAPE, flags=0, active_state=state)
            assert fired is False
            assert panic.is_panic() is False
            assert panic.get_panic_reason() is None

    def test_esc_key_synthetic_injected_is_ignored(self):
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)

        # Synthetic injected Esc (LLKHF_INJECTED) must never trigger panic
        fired = panic.check_key_event(
            VK_ESCAPE, flags=LLKHF_INJECTED, active_state="DRIVING"
        )
        assert fired is False
        assert panic.is_panic() is False
        assert panic.get_panic_reason() is None

    def test_ctrl_alt_p_hotkey_triggers_system_wide(self):
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)

        # Press Ctrl down
        assert panic.check_key_event(VK_CONTROL, flags=0, active_state="WATCHING") is False
        # Press Alt down
        assert panic.check_key_event(VK_MENU, flags=0, active_state="WATCHING") is False
        # Press P down while Ctrl and Alt are held
        fired = panic.check_key_event(VK_P, flags=0, active_state="WATCHING")

        assert fired is True
        assert panic.is_panic() is True
        assert panic.get_panic_reason() == PanicTriggerSource.CTRL_ALT_P

    def test_ctrl_alt_backspace_hotkey_triggers_system_wide(self):
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)

        # Press Ctrl down
        panic.check_key_event(VK_CONTROL, flags=0, active_state="THINKING")
        # Press Alt down
        panic.check_key_event(VK_MENU, flags=0, active_state="THINKING")
        # Press Backspace down
        fired = panic.check_key_event(VK_BACK, flags=0, active_state="THINKING")

        assert fired is True
        assert panic.is_panic() is True
        assert panic.get_panic_reason() == PanicTriggerSource.CTRL_ALT_BACKSPACE

    def test_ctrl_alt_with_altdown_flag(self):
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)

        # Press Ctrl down
        panic.check_key_event(VK_CONTROL, flags=0, active_state="WATCHING")
        # Press P with LLKHF_ALTDOWN flag set on the event itself
        fired = panic.check_key_event(VK_P, flags=LLKHF_ALTDOWN, active_state="WATCHING")

        assert fired is True
        assert panic.is_panic() is True
        assert panic.get_panic_reason() == PanicTriggerSource.CTRL_ALT_P

    def test_hotkey_synthetic_injection_ignored(self):
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)

        # Simulate synthetic Ctrl, Alt, P
        panic.check_key_event(VK_CONTROL, flags=LLKHF_INJECTED)
        panic.check_key_event(VK_MENU, flags=LLKHF_INJECTED)
        fired = panic.check_key_event(VK_P, flags=LLKHF_INJECTED)

        assert fired is False
        assert panic.is_panic() is False

    def test_key_up_releases_modifier_tracking(self):
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)

        # Press Ctrl down
        panic.check_key_event(VK_CONTROL, flags=0)
        # Release Ctrl up
        panic.check_key_event(VK_CONTROL, flags=LLKHF_UP)
        # Press Alt down
        panic.check_key_event(VK_MENU, flags=0)
        # Press P down - Ctrl is no longer down, should NOT trigger
        fired = panic.check_key_event(VK_P, flags=0)

        assert fired is False
        assert panic.is_panic() is False


class TestPanicManagerMouseAndCornerSlam:
    """Verifies screen corner slam detection and boundary math."""

    def test_corner_slam_primary_corners(self):
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, 0, 1920, 1080))
        panic = PanicManager(backend=backend)

        # Corners: (0, 0), (1919, 0), (0, 1079), (1919, 1079) with delta=4px
        test_corners = [
            (0, 0),
            (2, 2),
            (1919, 0),
            (1917, 3),
            (0, 1079),
            (3, 1078),
            (1919, 1079),
            (1918, 1077),
        ]

        for pt in test_corners:
            panic.reset_panic()
            fired = panic.check_mouse_position(pt[0], pt[1], flags=0)
            assert fired is True
            assert panic.is_panic() is True
            assert panic.get_panic_reason() == PanicTriggerSource.CORNER_SLAM

    def test_mid_screen_does_not_trigger_corner_slam(self):
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, 0, 1920, 1080))
        panic = PanicManager(backend=backend)

        safe_points = [
            (960, 540),
            (10, 10),
            (500, 500),
            (1900, 1000),
        ]

        for pt in safe_points:
            fired = panic.check_mouse_position(pt[0], pt[1], flags=0)
            assert fired is False
            assert panic.is_panic() is False

    def test_corner_slam_synthetic_mouse_ignored(self):
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, 0, 1920, 1080))
        panic = PanicManager(backend=backend)

        # Synthetic mouse injection at (0, 0)
        fired = panic.check_mouse_position(0, 0, flags=LLMHF_INJECTED)
        assert fired is False
        assert panic.is_panic() is False

    def test_corner_slam_disabled_via_config(self):
        config = SafetyConfig(corner_panic_enabled=False)
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, 0, 1920, 1080))
        panic = PanicManager(config=config, backend=backend)

        fired = panic.check_mouse_position(0, 0, flags=0)
        assert fired is False
        assert panic.is_panic() is False


class TestPanicManagerHardwareReleaseAndCallbacks:
    """Verifies hardware neutralization, callback notifications, and lifecycle."""

    def test_emergency_hardware_release_dispatches_cleanups(self):
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)

        # Trigger emergency release
        panic.emergency_hardware_release()

        # Check that backend received mouse release and keyboard modifier releases
        assert len(backend.events) > 0

        mouse_events = [e for e in backend.events if e.type == INPUT_MOUSE]
        assert len(mouse_events) == 1
        expected_mouse_flags = (
            MOUSEEVENTF_LEFTUP | MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_MIDDLEUP
        )
        assert mouse_events[0].flags == expected_mouse_flags

        key_events = [e for e in backend.events if e.type == INPUT_KEYBOARD]
        assert len(key_events) >= 3
        # All key events should have KEYEVENTF_KEYUP
        for k_ev in key_events:
            assert k_ev.flags & KEYEVENTF_KEYUP

    def test_callbacks_invoked_on_panic(self):
        backend = MockInputBackend()
        called_reasons: list[str] = []

        def callback_a(reason: str) -> None:
            called_reasons.append(f"A:{reason}")

        def callback_b(reason: str) -> None:
            called_reasons.append(f"B:{reason}")

        panic = PanicManager(backend=backend, on_panic_callback=callback_a)
        panic.register_callback(callback_b)

        panic.trigger_panic(PanicTriggerSource.MANUAL)

        assert called_reasons == ["A:manual", "B:manual"]
        assert panic.is_panic() is True
        assert panic.get_panic_reason() == PanicTriggerSource.MANUAL

    def test_reset_panic_restores_state(self):
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)

        panic.trigger_panic(PanicTriggerSource.ESC_KEY)
        assert panic.is_panic() is True

        panic.reset_panic()
        assert panic.is_panic() is False
        assert panic.get_panic_reason() is None
        assert not panic.get_panic_event().is_set()

    def test_thread_safety_trigger_and_event(self):
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)
        ready_flag = threading.Event()

        def worker():
            ready_flag.set()
            panic.get_panic_event().wait(timeout=2.0)

        t = threading.Thread(target=worker)
        t.start()
        ready_flag.wait(timeout=1.0)

        # Trigger panic from another thread
        panic.trigger_panic(PanicTriggerSource.MANUAL)
        t.join(timeout=1.0)
        assert not t.is_alive()
        assert panic.is_panic() is True


class TestPanicManagerCornerDebouncing:
    """Verifies edge-triggered 1.0-second corner slam debouncing."""

    def test_rapid_mouse_packets_in_corner_only_trip_once(self):
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, 0, 1920, 1080))
        callback = MagicMock()
        panic = PanicManager(backend=backend, on_panic_callback=callback)

        # Initial packet into top-left corner (0, 0)
        assert panic.check_mouse_position(0, 0, flags=0) is True
        assert panic.is_panic() is True
        assert panic.get_panic_reason() == PanicTriggerSource.CORNER_SLAM
        assert callback.call_count == 1

        # 50 subsequent mouse move packets within the same corner zone
        for offset in range(50):
            # Within delta=4 of (0, 0)
            x, y = offset % 4, (offset + 1) % 4
            fired = panic.check_mouse_position(x, y, flags=0)
            assert fired is False, f"Expected False on repeated packet {offset}"

        # Panic was triggered only once; callback called only once
        assert callback.call_count == 1
        assert panic.is_panic() is True

    def test_staying_in_corner_does_not_retrigger_after_cooldown(self, monkeypatch):
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, 0, 1920, 1080))
        callback = MagicMock()
        panic = PanicManager(backend=backend, on_panic_callback=callback)

        current_time = 100.0
        monkeypatch.setattr(time, "monotonic", lambda: current_time)

        # First entry at t=100.0
        assert panic.check_mouse_position(0, 0, flags=0) is True
        assert callback.call_count == 1

        # Advance time by 2.0s (well past the 1.0s debounce time) while remaining in corner
        current_time = 102.0
        fired = panic.check_mouse_position(0, 0, flags=0)
        assert fired is False
        assert callback.call_count == 1

        # Advance time by another 10.0s, still in corner
        current_time = 112.0
        fired = panic.check_mouse_position(1, 1, flags=0)
        assert fired is False
        assert callback.call_count == 1

    def test_exiting_corner_and_reentering_before_cooldown_does_not_trigger(self, monkeypatch):
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, 0, 1920, 1080))
        callback = MagicMock()
        panic = PanicManager(backend=backend, on_panic_callback=callback)

        current_time = 100.0
        monkeypatch.setattr(time, "monotonic", lambda: current_time)

        # First entry at t=100.0
        assert panic.check_mouse_position(0, 0, flags=0) is True
        assert callback.call_count == 1
        assert panic._in_corner_zone is True

        # Move outside corner (e.g. center of screen)
        current_time = 100.2
        assert panic.check_mouse_position(500, 500, flags=0) is False
        assert panic._in_corner_zone is False

        # Re-enter corner at t=100.5 (only 0.5s elapsed, < 1.0s debounce)
        current_time = 100.5
        fired = panic.check_mouse_position(0, 0, flags=0)
        assert fired is False
        assert callback.call_count == 1
        assert panic._in_corner_zone is True

    def test_exiting_corner_and_waiting_cooldown_reenables_trigger(self, monkeypatch):
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, 0, 1920, 1080))
        callback = MagicMock()
        panic = PanicManager(backend=backend, on_panic_callback=callback)

        current_time = 100.0
        monkeypatch.setattr(time, "monotonic", lambda: current_time)

        # 1. First trigger at t=100.0
        assert panic.check_mouse_position(0, 0, flags=0) is True
        assert callback.call_count == 1

        # 2. Exit corner to center
        current_time = 100.3
        assert panic.check_mouse_position(960, 540, flags=0) is False
        assert panic._in_corner_zone is False

        # 3. Wait until t=101.1 (1.1s >= 1.0s debounce elapsed)
        current_time = 101.1
        # Re-enter different corner (top-right: 1919, 0)
        assert panic.check_mouse_position(1919, 0, flags=0) is True
        assert callback.call_count == 2

        # 4. Exit corner again
        current_time = 101.4
        assert panic.check_mouse_position(960, 540, flags=0) is False

        # 5. Re-enter at t=101.9 (< 1.0s since 101.1) -> should NOT trigger
        current_time = 101.9
        assert panic.check_mouse_position(0, 1079, flags=0) is False
        assert callback.call_count == 2

        # 6. Exit again and re-enter at t=102.2 (1.1s since 101.1) -> should trigger
        current_time = 102.0
        assert panic.check_mouse_position(960, 540, flags=0) is False
        current_time = 102.2
        assert panic.check_mouse_position(0, 1079, flags=0) is True
        assert callback.call_count == 3

    def test_reset_panic_clears_corner_debounce_state(self):
        backend = MockInputBackend(screen_metrics=(1920, 1080, 0, 0, 1920, 1080))
        panic = PanicManager(backend=backend)

        # Trigger corner panic
        assert panic.check_mouse_position(0, 0, flags=0) is True
        assert panic._in_corner_zone is True
        assert panic._last_corner_slam_time > 0.0

        # Reset panic
        panic.reset_panic()
        assert panic._in_corner_zone is False
        assert panic._last_corner_slam_time == 0.0
        assert panic.is_panic() is False

        # Can trigger corner slam again immediately
        assert panic.check_mouse_position(0, 0, flags=0) is True
        assert panic.is_panic() is True


class TestPanicManagerHardKillTermination:
    """Verifies unblocked Ctrl+Alt+K taskkill and os._exit(1) termination."""

    def test_ctrl_alt_k_triggers_immediate_hard_kill_unblocked(self, monkeypatch):
        mock_popen = MagicMock()
        mock_exit = MagicMock()
        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        monkeypatch.setattr(os, "_exit", mock_exit)

        callback = MagicMock()
        backend = MockInputBackend()
        panic = PanicManager(backend=backend)
        panic.register_callback(callback)
        panic.allow_process_exit = True

        panic.trigger_panic(PanicTriggerSource.CTRL_ALT_K_KILL)

        # Verified: callback is NOT called because hard_kill occurs before callbacks
        assert callback.call_count == 0

        # Verified: subprocess.Popen called with taskkill /F /T /PID <pid>
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        cmd = args[0]
        assert cmd[:4] == ["taskkill", "/F", "/T", "/PID"]
        assert cmd[4] == str(os.getpid())
        assert kwargs.get("creationflags") == 0x08000000
        assert kwargs.get("stdout") == subprocess.DEVNULL
        assert kwargs.get("stderr") == subprocess.DEVNULL

        # Verified: os._exit(1) called immediately with exit code 1
        mock_exit.assert_called_once_with(1)

    def test_hard_kill_all_processes_releases_hardware_before_kill(self, monkeypatch):
        mock_popen = MagicMock()
        mock_exit = MagicMock()
        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        monkeypatch.setattr(os, "_exit", mock_exit)

        backend = MockInputBackend()
        panic = PanicManager(backend=backend)

        panic.hard_kill_all_processes()

        # Hardware events were dispatched
        assert len(backend.events) > 0
        mouse_events = [e for e in backend.events if e.type == INPUT_MOUSE]
        assert len(mouse_events) == 1
        key_events = [e for e in backend.events if e.type == INPUT_KEYBOARD]
        assert len(key_events) >= 3

        # Taskkill and exit(1) executed
        mock_popen.assert_called_once()
        mock_exit.assert_called_once_with(1)

    def test_ctrl_alt_k_when_allow_process_exit_is_false(self, monkeypatch):
        mock_popen = MagicMock()
        mock_exit = MagicMock()
        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        monkeypatch.setattr(os, "_exit", mock_exit)

        callback = MagicMock()
        backend = MockInputBackend()
        panic = PanicManager(backend=backend, on_panic_callback=callback)
        panic.allow_process_exit = False

        panic.trigger_panic(PanicTriggerSource.CTRL_ALT_K_KILL)

        # When allow_process_exit is False, does not kill or exit
        mock_popen.assert_not_called()
        mock_exit.assert_not_called()

        # Normal callbacks run
        assert callback.call_count == 1
        callback.assert_called_once_with(PanicTriggerSource.CTRL_ALT_K_KILL)

    def test_check_key_event_ctrl_alt_k_invokes_hard_kill_when_exit_allowed(self, monkeypatch):
        mock_popen = MagicMock()
        mock_exit = MagicMock()
        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        monkeypatch.setattr(os, "_exit", mock_exit)

        backend = MockInputBackend()
        panic = PanicManager(backend=backend)
        panic.allow_process_exit = True

        # Ctrl down
        panic.check_key_event(VK_CONTROL, flags=0)
        # Alt down
        panic.check_key_event(VK_MENU, flags=0)
        # Press K
        fired = panic.check_key_event(VK_K, flags=0)

        assert fired is True
        mock_popen.assert_called_once()
        mock_exit.assert_called_once_with(1)

    def test_check_key_event_ctrl_alt_q_invokes_hard_kill_when_exit_allowed(self, monkeypatch):
        mock_popen = MagicMock()
        mock_exit = MagicMock()
        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        monkeypatch.setattr(os, "_exit", mock_exit)

        backend = MockInputBackend()
        panic = PanicManager(backend=backend)
        panic.allow_process_exit = True

        # Ctrl down
        panic.check_key_event(VK_CONTROL, flags=0)
        # Alt down
        panic.check_key_event(VK_MENU, flags=0)
        # Press Q
        fired = panic.check_key_event(VK_Q, flags=0)

        assert fired is True
        mock_popen.assert_called_once()
        mock_exit.assert_called_once_with(1)
