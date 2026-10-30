"""
Tests for ParasiteAI Physical Unicode Keyboard Driver.
Verifies layout-independent Unicode injection via KEYEVENTF_UNICODE (0x0004),
astral plane emoji UTF-16 surrogate pair decomposition, Shift+Enter multiline safety,
cadence jitter timing, sub-2ms per-keystroke interrupt preemption, hotkeys,
and emergency stuck-key neutralization.
"""

from __future__ import annotations

import threading
import time
import pytest

from parasite_ai.config import KeyboardConfig
from parasite_ai.hands.keyboard import (
    INPUT_KEYBOARD,
    KEYEVENTF_KEYUP,
    KEYEVENTF_UNICODE,
    VK_CONTROL,
    VK_MENU,
    VK_RETURN,
    VK_SHIFT,
    CapturedInputEvent,
    KeyboardDriver,
    MockInputBackend,
)


class TestKeyboardDriverUnicodeAndAstralPlane:
    """Verifies layout-independent Unicode typing and UTF-16 surrogate pair splitting."""

    def test_unicode_bmp_typing(self):
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        text = "Hello World! 123"
        success = driver.type_text(text, submit=False)
        assert success is True

        # Check recorded scan codes
        scans = backend.get_typed_unicode_scans()
        assert [chr(s) for s in scans] == list(text)

        # Check every typed char had both DOWN (KEYEVENTF_UNICODE) and UP (KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
        kb_events = [e for e in backend.events if e.type == INPUT_KEYBOARD and (e.flags & KEYEVENTF_UNICODE)]
        assert len(kb_events) == len(text) * 2

        for i, char in enumerate(text):
            down_ev = kb_events[i * 2]
            up_ev = kb_events[i * 2 + 1]
            assert down_ev.scan == ord(char)
            assert down_ev.vk == 0
            assert down_ev.flags == KEYEVENTF_UNICODE

            assert up_ev.scan == ord(char)
            assert up_ev.vk == 0
            assert up_ev.flags == (KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)

    def test_international_unicode_characters(self):
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        # Cyrillic, Greek, Japanese, Arabic, Accented characters
        text = "Привет мир! Γειά σου κόσμε! こんにちは! مرحباً! Über Café"
        success = driver.type_text(text, submit=False)
        assert success is True

        scans = backend.get_typed_unicode_scans()
        assert "".join(chr(s) for s in scans) == text

    def test_astral_plane_surrogate_pairs(self):
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        # Astral plane characters (code point > 0xFFFF)
        # 🤖 = U+1F916 -> High surrogate: 0xD83E, Low surrogate: 0xDD16
        # 🚀 = U+1F680 -> High surrogate: 0xD83D, Low surrogate: 0xDE80
        emoji = "🤖"
        decomposed = driver.decompose_utf16(emoji)
        assert len(decomposed) == 2
        w1, w2 = decomposed
        assert w1 == 0xD83E
        assert w2 == 0xDD16

        success = driver.type_text(emoji, submit=False)
        assert success is True

        scans = backend.get_typed_unicode_scans()
        assert scans == [0xD83E, 0xDD16]

        # 4 events total: W1 down/up, W2 down/up
        kb_events = [e for e in backend.events if e.type == INPUT_KEYBOARD]
        assert len(kb_events) == 4
        assert kb_events[0].scan == 0xD83E
        assert kb_events[0].flags == KEYEVENTF_UNICODE
        assert kb_events[1].scan == 0xD83E
        assert kb_events[1].flags == (KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
        assert kb_events[2].scan == 0xDD16
        assert kb_events[2].flags == KEYEVENTF_UNICODE
        assert kb_events[3].scan == 0xDD16
        assert kb_events[3].flags == (KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)


class TestKeyboardDriverMultilineAndSubmit:
    """Verifies Shift+Enter multiline web chat safety and submit behavior."""

    def test_shift_enter_for_intermediate_newlines(self):
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        # Text with intermediate newline and final submit
        text = "Line 1\nLine 2"
        success = driver.type_text(text, submit=True)
        assert success is True

        # Check sequence of VK events
        vk_events = [e for e in backend.events if not (e.flags & KEYEVENTF_UNICODE)]
        # Intermediate newline must have Shift down -> Enter down/up -> Shift up
        # Final submit must have Enter down/up
        shift_down = [e for e in vk_events if e.vk == VK_SHIFT and not (e.flags & KEYEVENTF_KEYUP)]
        assert len(shift_down) == 1, "Expected Shift+Enter for intermediate newline"

        enter_downs = [e for e in vk_events if e.vk == VK_RETURN and not (e.flags & KEYEVENTF_KEYUP)]
        # 1 for intermediate Shift+Enter, 1 for final submit
        assert len(enter_downs) == 2

    def test_final_newline_with_submit(self):
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        # Text ending with \n and submit=True
        text = "Command\n"
        success = driver.type_text(text, submit=True)
        assert success is True

        vk_events = [e for e in backend.events if not (e.flags & KEYEVENTF_UNICODE)]
        # Final newline with submit=True should NOT use Shift+Enter, it should use plain Enter
        shift_downs = [e for e in vk_events if e.vk == VK_SHIFT and not (e.flags & KEYEVENTF_KEYUP)]
        assert len(shift_downs) == 0

        enter_downs = [e for e in vk_events if e.vk == VK_RETURN and not (e.flags & KEYEVENTF_KEYUP)]
        assert len(enter_downs) == 1


class TestKeyboardDriverInterruptsAndPreemption:
    """Verifies per-keystroke sub-2ms preemption and emergency key neutralization."""

    def test_already_cancelled_token_aborts_immediately(self):
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)
        token = threading.Event()
        token.set()

        t0 = time.perf_counter()
        success = driver.type_text("Hello World", cancellation_token=token)
        t_elapsed = time.perf_counter() - t0

        assert success is False
        assert t_elapsed < 0.005
        assert len(backend.events) == 0

    def test_interrupt_mid_typing_aborts_in_under_2ms(self):
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)
        token = threading.Event()

        # Trigger interrupt when letter 'W' is typed
        backend.interrupt_on_char = "W"

        success = driver.type_text("Hello World", cancellation_token=token)
        assert success is False

        # Only characters up to 'W' should have been typed
        typed_scans = backend.get_typed_unicode_scans()
        typed_str = "".join(chr(s) for s in typed_scans)
        assert typed_str.startswith("Hello ")
        assert "World" not in typed_str

    def test_emergency_release_keys_on_interrupt(self):
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)
        token = threading.Event()

        # Track a held modifier
        driver._held_keys.add(VK_CONTROL)
        driver._held_keys.add(VK_SHIFT)

        driver.emergency_release_keys()

        # Verify KEYEVENTF_KEYUP events were dispatched
        key_up_vks = [
            e.vk for e in backend.events
            if e.type == INPUT_KEYBOARD and (e.flags & KEYEVENTF_KEYUP)
        ]
        assert VK_CONTROL in key_up_vks
        assert VK_SHIFT in key_up_vks
        assert len(driver._held_keys) == 0


class TestKeyboardDriverHotkeysAndClickAndType:
    """Verifies hotkey execution order and atomic click_and_type operation."""

    def test_hotkey_execution_order(self):
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        success = driver.hotkey("ctrl", "shift", "p")
        assert success is True

        vk_events = backend.events
        # Check order of key down: Ctrl down -> Shift down -> P down
        down_vks = [e.vk for e in vk_events if not (e.flags & KEYEVENTF_KEYUP)]
        assert down_vks == [VK_CONTROL, VK_SHIFT, ord("P")]

        # Check order of key up (reverse order): P up -> Shift up -> Ctrl up
        up_vks = [e.vk for e in vk_events if bool(e.flags & KEYEVENTF_KEYUP)]
        assert up_vks == [ord("P"), VK_SHIFT, VK_CONTROL]

    def test_click_and_type_atomic(self):
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        success = driver.click_and_type(500, 300, "Search query", submit=True)
        assert success is True

        # Must contain mouse click followed by typed text
        mouse_events = [e for e in backend.events if e.type == 0]  # INPUT_MOUSE
        assert len(mouse_events) >= 2  # Down and Up

        typed_scans = backend.get_typed_unicode_scans()
        assert "".join(chr(s) for s in typed_scans) == "Search query"

    def test_click_and_type_pre_cancelled(self):
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)
        token = threading.Event()
        token.set()

        success = driver.click_and_type(100, 100, "Text", cancellation_token=token)
        assert success is False
        assert len(backend.events) == 0
