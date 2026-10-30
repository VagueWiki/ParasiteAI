"""
Unit and integration tests for Win32 Low-Level Hardware Hook Interrupt & Safety Guard.
Verifies <2ms preemption, synthetic event filtering, panic triggers, and sliding cooldown.
"""

from __future__ import annotations

import ctypes
import threading
import time
from unittest.mock import MagicMock

import pytest

from parasite_ai.safety.interrupt_guard import (
    InterruptGuard,
    KBDLLHOOKSTRUCT,
    LLKHF_INJECTED,
    LLKHF_UP,
    LLMHF_INJECTED,
    MSLLHOOKSTRUCT,
    POINT,
    VK_BACK,
    VK_CONTROL,
    VK_ESCAPE,
    VK_MENU,
    VK_P,
    WH_KEYBOARD_LL,
    WH_MOUSE_LL,
)


class TestInterruptGuardStructs:
    """Verifies ctypes structure sizes and alignments matching 64-bit Win32 ABI."""

    def test_ctypes_struct_memory_layout(self):
        assert ctypes.sizeof(POINT) == 8
        assert ctypes.sizeof(MSLLHOOKSTRUCT) == 32
        assert ctypes.sizeof(KBDLLHOOKSTRUCT) == 24

        # Verify field offsets
        assert MSLLHOOKSTRUCT.pt.offset == 0
        assert MSLLHOOKSTRUCT.mouseData.offset == 8
        assert MSLLHOOKSTRUCT.flags.offset == 12
        assert MSLLHOOKSTRUCT.time.offset == 16
        assert MSLLHOOKSTRUCT.dwExtraInfo.offset == 24

        assert KBDLLHOOKSTRUCT.vkCode.offset == 0
        assert KBDLLHOOKSTRUCT.scanCode.offset == 4
        assert KBDLLHOOKSTRUCT.flags.offset == 8
        assert KBDLLHOOKSTRUCT.time.offset == 12
        assert KBDLLHOOKSTRUCT.dwExtraInfo.offset == 16


class TestInterruptGuardFilteringAndPreemption:
    """Tests synthetic vs physical event filtering, preemption latency, and panic triggers."""

    def test_synthetic_mouse_event_ignored(self):
        guard = InterruptGuard(cooldown_seconds=1.0)
        token = guard.get_cancellation_token()

        assert not guard.is_interrupted()
        assert not token.is_set()

        # Simulate synthetic mouse movement (LLMHF_INJECTED = 1)
        guard.simulate_event("mouse", flags=LLMHF_INJECTED, pt=(500, 500))

        assert not guard.is_interrupted()
        assert not token.is_set()

    def test_physical_mouse_event_aborts_under_2ms(self):
        guard = InterruptGuard(cooldown_seconds=1.0)
        token = guard.get_cancellation_token()

        start = time.perf_counter()
        # Physical mouse event has flags = 0
        guard.simulate_event("mouse", flags=0, pt=(500, 500))
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert guard.is_interrupted()
        assert token.is_set()
        # Must execute within sub-2ms budget
        assert elapsed_ms < 2.0

    def test_synthetic_keyboard_event_ignored(self):
        guard = InterruptGuard(cooldown_seconds=1.0)
        token = guard.get_cancellation_token()

        # Simulate synthetic keystroke (LLKHF_INJECTED = 0x10)
        guard.simulate_event("keyboard", flags=LLKHF_INJECTED, vk_code=65)

        assert not guard.is_interrupted()
        assert not token.is_set()

    def test_physical_keyboard_event_aborts_under_2ms(self):
        guard = InterruptGuard(cooldown_seconds=1.0)
        token = guard.get_cancellation_token()

        start = time.perf_counter()
        # Physical keyboard event has flags = 0
        guard.simulate_event("keyboard", flags=0, vk_code=65)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert guard.is_interrupted()
        assert token.is_set()
        assert elapsed_ms < 2.0

    def test_panic_key_escape(self):
        panic_mock = MagicMock()
        guard = InterruptGuard(cooldown_seconds=1.0, on_panic_callback=panic_mock)

        assert not guard.is_panic()
        # Physical Esc key press
        guard.simulate_event("keyboard", flags=0, vk_code=VK_ESCAPE)

        assert guard.is_interrupted()
        assert guard.is_panic()
        assert guard.panic_manager.get_panic_reason() == "esc_key"
        panic_mock.assert_called_once_with("esc_key")

    def test_panic_key_ctrl_alt_p(self):
        guard = InterruptGuard(cooldown_seconds=1.0)

        # Simulate Ctrl Down, Alt Down, then P Down
        guard.simulate_event("keyboard", flags=0, vk_code=VK_CONTROL)
        guard.simulate_event("keyboard", flags=0, vk_code=VK_MENU)
        guard.simulate_event("keyboard", flags=0, vk_code=VK_P)

        assert guard.is_interrupted()
        assert guard.is_panic()
        assert guard.panic_manager.get_panic_reason() == "ctrl_alt_p"

    def test_panic_key_ctrl_alt_backspace(self):
        guard = InterruptGuard(cooldown_seconds=1.0)

        # Simulate Ctrl Down, Alt Down, then Backspace Down
        guard.simulate_event("keyboard", flags=0, vk_code=VK_CONTROL)
        guard.simulate_event("keyboard", flags=0, vk_code=VK_MENU)
        guard.simulate_event("keyboard", flags=0, vk_code=VK_BACK)

        assert guard.is_interrupted()
        assert guard.is_panic()
        assert guard.panic_manager.get_panic_reason() == "ctrl_alt_backspace"

    def test_corner_panic_detection(self):
        guard = InterruptGuard(cooldown_seconds=1.0, corner_panic_enabled=True, corner_distance_px=4)

        # Coordinate (2, 2) is <= 4px from (0, 0)
        guard.simulate_event("mouse", flags=0, pt=(2, 2))

        assert guard.is_interrupted()
        assert guard.is_panic()
        assert guard.panic_manager.get_panic_reason() == "corner_slam"

    def test_corner_panic_ignored_when_disabled(self):
        guard = InterruptGuard(cooldown_seconds=1.0, corner_panic_enabled=False, corner_distance_px=4)

        guard.simulate_event("mouse", flags=0, pt=(2, 2))

        # Physical touch interrupt should fire, but NOT panic
        assert guard.is_interrupted()
        assert not guard.is_panic()


class TestInterruptGuardCooldownAndLifecycle:
    """Tests sliding cooldown window, manual reset, wait_interruptible, and thread lifecycle."""

    def test_sliding_cooldown_window(self):
        guard = InterruptGuard(cooldown_seconds=0.2)
        rearm_mock = MagicMock()
        guard._on_rearm_callback = rearm_mock

        # First touch
        guard.simulate_event("mouse", flags=0, pt=(500, 500))
        assert guard.is_interrupted()

        # Wait 0.1s, then touch again (slides window)
        time.sleep(0.1)
        guard.simulate_event("mouse", flags=0, pt=(500, 500))
        assert guard.is_interrupted()

        # After another 0.12s (total 0.22s since first, but only 0.12s since second)
        time.sleep(0.12)
        assert guard.is_interrupted()

        # Wait for sliding cooldown to completely expire (0.15s more)
        time.sleep(0.15)
        assert not guard.is_interrupted()
        assert not guard.get_cancellation_token().is_set()

    def test_manual_reset_interrupt(self):
        guard = InterruptGuard(cooldown_seconds=10.0)

        guard.simulate_event("keyboard", flags=0, vk_code=VK_ESCAPE)
        assert guard.is_interrupted()
        assert guard.is_panic()

        guard.reset_interrupt()

        assert not guard.is_interrupted()
        assert not guard.is_panic()
        assert not guard.get_cancellation_token().is_set()

    def test_wait_interruptible_wakes_immediately(self):
        guard = InterruptGuard(cooldown_seconds=1.0)

        def trigger_interrupt():
            time.sleep(0.03)
            guard.simulate_event("mouse", flags=0, pt=(500, 500))

        th = threading.Thread(target=trigger_interrupt)
        th.start()

        start = time.perf_counter()
        # Should normally wait up to 2.0s, but wake immediately when thread fires at ~0.03s
        completed = guard.wait_interruptible(timeout=2.0)
        elapsed = time.perf_counter() - start

        th.join()

        assert not completed  # False means interrupted
        assert elapsed < 0.2

    def test_hook_lifecycle_start_stop(self):
        guard = InterruptGuard(cooldown_seconds=1.0)
        guard.start()
        assert guard._is_running

        # Stop cleanly
        guard.stop()
        assert not guard._is_running

    def test_interrupt_callback_invoked(self):
        cb_mock = MagicMock()
        guard = InterruptGuard(cooldown_seconds=1.0, on_interrupt_callback=cb_mock)

        guard.simulate_event("mouse", flags=0, pt=(500, 500))
        cb_mock.assert_called_once()
        assert "mouse" in cb_mock.call_args[0][0]
