"""
Tests for ParasiteAI Global Panic Abort Subsystem.
Verifies emergency panic triggers (Esc, Ctrl+Alt+P, Ctrl+Alt+Backspace, Screen Corner Slam),
synthetic input filtering, multi-callback notification, emergency hardware state neutralization,
and panic reset lifecycle.
"""

from __future__ import annotations

import threading
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
from parasite_ai.safety.panic import PanicManager, PanicTriggerSource


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
