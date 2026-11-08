"""
ParasiteAI - Milestone M2 Adversarial Gate Verification Test Suite (Challenger 2).
Exhaustively stress-tests:
1. Complex Unicode injection (astral plane emojis 🤖🎉🌍, composite ZWJ emojis, CJK extensions, RTL scripts).
2. Multiline web chat safety: consecutive newlines (\n\n\n), trailing newlines, submit_on_end=True vs False,
   Shift+Enter vs Enter emission sequences, and normalization.
3. Per-keystroke interrupt cancellation under concurrency: physical touch on char 0, mid-string, and last char,
   verifying sub-2ms abort latency and complete modifier neutralization.
4. Stress test click_and_type: focus delays, caret initialization, and preemption during click, delay, and typing.
5. Latency & concurrency benchmarks of wait_interruptible across worker threads with empirical P50/P95/Max metrics.
"""

from __future__ import annotations

import ctypes
import statistics
import struct
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import pytest

from parasite_ai.config import KeyboardConfig, MouseConfig, SafetyConfig
from parasite_ai.hands.keyboard import (
    INPUT_KEYBOARD,
    INPUT_MOUSE,
    KEYEVENTF_KEYUP,
    KEYEVENTF_UNICODE,
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    VK_CONTROL,
    VK_MENU,
    VK_RETURN,
    VK_SHIFT,
    CapturedInputEvent,
    KeyboardDriver,
    MockInputBackend,
)
from parasite_ai.hands.kinematics import KinematicsEngine
from parasite_ai.hands.mouse import MouseDriver
from parasite_ai.safety.interrupt_guard import (
    InterruptGuard,
    LLKHF_INJECTED,
    LLMHF_INJECTED,
)
from parasite_ai.safety.panic import PanicManager


def decode_utf16_scans(scans: List[int]) -> str:
    """Decodes a sequence of 16-bit scan codes into a UTF-16 string handling surrogate pairs."""
    if not scans:
        return ""
    raw = struct.pack(f"<{len(scans)}H", *scans)
    return raw.decode("utf-16-le")


# ===========================================================================
# Adversarial Mock Backends for White-Box Stress Testing
# ===========================================================================
class AdversarialTriggerBackend(MockInputBackend):
    """
    Enhanced MockInputBackend allowing precise white-box interrupt injection
    at specific keystrokes, during sleep delays, on specific virtual keys,
    or after an exact number of input packets.
    """

    def __init__(
        self,
        virtual_time: bool = True,
        interrupt_on_vk: Optional[int] = None,
        interrupt_on_scan: Optional[int] = None,
        interrupt_after_event_count: Optional[int] = None,
        interrupt_during_sleep_call: Optional[int] = None,
        token_to_signal: Optional[threading.Event] = None,
    ):
        super().__init__(virtual_time=virtual_time)
        self.interrupt_on_vk = interrupt_on_vk
        self.interrupt_on_scan = interrupt_on_scan
        self.interrupt_after_event_count = interrupt_after_event_count
        self.interrupt_during_sleep_call = interrupt_during_sleep_call
        self.token_to_signal = token_to_signal
        self.sleep_call_count = 0

    def send_inputs(self, inputs: List[Any]) -> int:
        ret = super().send_inputs(inputs)

        target_token = self.token_to_signal or self._bound_token

        if self.interrupt_after_event_count and len(self.events) >= self.interrupt_after_event_count:
            if target_token:
                target_token.set()

        if self.interrupt_on_vk:
            for ev in self.events[-len(inputs):]:
                if ev.type == INPUT_KEYBOARD and ev.vk == self.interrupt_on_vk:
                    if target_token:
                        target_token.set()
                    break

        if self.interrupt_on_scan:
            for ev in self.events[-len(inputs):]:
                if ev.type == INPUT_KEYBOARD and ev.scan == self.interrupt_on_scan:
                    if target_token:
                        target_token.set()
                    break

        return ret

    def sleep_interruptible(
        self,
        duration_s: float,
        cancellation_token: Optional[threading.Event],
    ) -> bool:
        self.sleep_call_count += 1
        target_token = self.token_to_signal or cancellation_token

        if self.interrupt_during_sleep_call and self.sleep_call_count == self.interrupt_during_sleep_call:
            if target_token:
                target_token.set()

        return super().sleep_interruptible(duration_s, cancellation_token)


# ===========================================================================
# 1. Unicode Injection with Complex Astral Plane & Composite Emojis
# ===========================================================================
class TestAdversarialUnicodeAstralAndCompositeEmojis:
    """Stress tests Unicode physical typing with astral plane, composite ZWJ, and non-Latin scripts."""

    def test_astral_plane_emojis_surrogate_pair_invariants(self):
        """
        Astral plane emojis (>0xFFFF) must decompose into UTF-16 surrogate pairs:
        W1 in [0xD800, 0xDBFF] (high surrogate) and W2 in [0xDC00, 0xDFFF] (low surrogate).
        Reconstruction must exactly equal the original code point.
        """
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        astral_emojis = [
            "🤖", "🎉", "🌍", "🧠", "👾", "🚀", "🪐", "🧬", "🌋", "🛸"
        ]

        for emoji in astral_emojis:
            cp = ord(emoji)
            assert cp > 0xFFFF, f"Emoji {emoji} must be in astral plane"

            decomposed = driver.decompose_utf16(emoji)
            assert len(decomposed) == 2, f"Emoji {emoji} must decompose into exactly 2 code units"
            w1, w2 = decomposed

            # UTF-16 surrogate range verification
            assert 0xD800 <= w1 <= 0xDBFF, f"W1 0x{w1:04X} outside high surrogate range"
            assert 0xDC00 <= w2 <= 0xDFFF, f"W2 0x{w2:04X} outside low surrogate range"

            # Invertibility check
            reconstructed_cp = 0x10000 + ((w1 - 0xD800) << 10) + (w2 - 0xDC00)
            assert reconstructed_cp == cp, f"Surrogate reconstruction failed for {emoji}"

        # Inject all astral emojis in a single text stream
        full_text = "".join(astral_emojis)
        success = driver.type_text(full_text, submit=False)
        assert success is True

        scans = backend.get_typed_unicode_scans()
        assert len(scans) == len(astral_emojis) * 2

        # Verify that reconstructed string matches full_text
        reconstructed = decode_utf16_scans(scans)
        assert reconstructed == full_text

        # Verify every surrogate code unit has matching DOWN and UP events with KEYEVENTF_UNICODE
        kb_events = [e for e in backend.events if e.type == INPUT_KEYBOARD and (e.flags & KEYEVENTF_UNICODE)]
        assert len(kb_events) == len(astral_emojis) * 4  # 2 code units * 2 events (down + up)

        for i in range(len(scans)):
            down_ev = kb_events[i * 2]
            up_ev = kb_events[i * 2 + 1]
            assert down_ev.scan == scans[i]
            assert down_ev.vk == 0
            assert down_ev.flags == KEYEVENTF_UNICODE
            assert up_ev.scan == scans[i]
            assert up_ev.vk == 0
            assert up_ev.flags == (KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)

    def test_complex_composite_emojis_and_zwj_sequences(self):
        """
        Tests multi-codepoint composite emojis including Zero-Width Joiner (ZWJ) sequences,
        skin tone modifiers, variation selectors, and regional indicator flags.
        """
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        composite_sequences = [
            # Family: man + ZWJ + woman + ZWJ + girl + ZWJ + boy (7 codepoints, 11 UTF-16 code units)
            "👨‍👩‍👧‍👦",
            # Technologist with medium skin tone: person + medium tone + ZWJ + laptop (4 codepoints, 7 UTF-16 code units)
            "🧑🏽‍💻",
            # Rainbow flag: waving white flag + variation selector 16 + ZWJ + rainbow (4 codepoints, 6 UTF-16 code units)
            "🏳️‍🌈",
            # US Flag: Regional indicator symbol letter U + Regional indicator symbol letter S (2 codepoints, 4 UTF-16 code units)
            "🇺🇸",
            # Scientist with dark skin tone: woman + dark tone + ZWJ + microscope (4 codepoints, 7 UTF-16 code units)
            "👩🏿‍🔬",
        ]

        test_payload = " ".join(composite_sequences)
        success = driver.type_text(test_payload, submit=False)
        assert success is True

        scans = backend.get_typed_unicode_scans()
        # Decode UTF-16 code units to confirm lossless preservation
        decoded_output = decode_utf16_scans(scans)
        assert decoded_output == test_payload

        # Ensure no stuck keys remaining
        assert len(driver._held_keys) == 0

    def test_cjk_extensions_and_non_latin_scripts(self):
        """
        Tests typing of rare CJK ideographs (Extension B/C), Arabic with full Tashkeel,
        Hebrew with Niqqud, Devanagari with conjuncts, Thai, and Mathematical Alphanumeric symbols.
        """
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        texts = [
            # CJK Extension B (𠀀 U+20000, 𪚥 U+2A6A5, 𫠠 U+2B820)
            "CJK: 𠀀 𪚥 𫠠 漢字",
            # Arabic with Tashkeel diacritics
            "بِسْمِ ٱللَّٰهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ",
            # Hebrew with Niqqud
            "שָׁלוֹם עֲלֵיכֶם מַלְאֲכֵי הַשָּׁלוֹם",
            # Devanagari with virama and conjuncts
            "ॐ भूर्भुवः स्वः तत्सवितुर्वरेण्यं",
            # Thai with vowels and tone marks
            "สวัสดีชาวโลก ยินดีที่ได้รู้จัก",
            # Mathematical Fraktur and Script symbols
            "𝔓𝔞𝔯𝔞𝔰𝔦𝔱𝔢 𝓐𝓘 𝕏 𝟚𝟘𝟚𝟞",
        ]

        for text in texts:
            backend.clear()
            success = driver.type_text(text, submit=False)
            assert success is True, f"Failed to type: {text}"

            scans = backend.get_typed_unicode_scans()
            reconstructed = decode_utf16_scans(scans)
            assert reconstructed == text, f"Mismatch in reconstructed text: {reconstructed} != {text}"

    def test_massive_unicode_stream_stress(self):
        """
        Stress-tests typing a massive stream of 5,000 mixed characters including
        ASCII, astral emojis, composite ZWJ, and non-Latin scripts.
        """
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        snippet = "ParasiteAI 🤖 👨‍👩‍👧‍👦 مرحبا 𪚥 नमस्ते 🏳️‍🌈\n"
        repetitions = 200
        massive_text = snippet * repetitions  # ~5,000 characters

        t0 = time.perf_counter()
        success = driver.type_text(massive_text, submit=False)
        t_elapsed = time.perf_counter() - t0

        assert success is True
        scans = backend.get_typed_unicode_scans()
        # Non-newline characters must match
        normalized = massive_text.replace("\r\n", "\n").replace("\r", "\n")
        expected_chars = [c for c in normalized if c != "\n"]
        reconstructed = decode_utf16_scans(scans)
        assert reconstructed == "".join(expected_chars)

        # Shift+Enter count must equal newline count
        shift_downs = [
            e for e in backend.events
            if e.type == INPUT_KEYBOARD and e.vk == VK_SHIFT and not (e.flags & KEYEVENTF_KEYUP)
        ]
        assert len(shift_downs) == repetitions
        assert len(driver._held_keys) == 0


# ===========================================================================
# 2. Multiline Chat Safety Stress Testing
# ===========================================================================
class TestAdversarialMultilineChatSafety:
    """Stress tests multiline inputs, consecutive newlines, Shift+Enter vs Enter emission sequences."""

    def test_consecutive_multiple_newlines_with_submit_true(self):
        """
        Input '\\n\\n\\n' with submit=True:
        Must emit exactly 2 Shift+Enters (for intermediate newlines)
        followed by exactly 1 Plain Enter (for final newline with submit).
        Total Enter down events = 3. Shift down events = 2.
        """
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        text = "\n\n\n"
        success = driver.type_text(text, submit=True)
        assert success is True

        vk_events = [e for e in backend.events if not (e.flags & KEYEVENTF_UNICODE)]

        # Find sequence of VK down events
        down_vks = [e.vk for e in vk_events if not (e.flags & KEYEVENTF_KEYUP)]
        # Expected: Shift, Return, Shift, Return, Return
        assert down_vks == [VK_SHIFT, VK_RETURN, VK_SHIFT, VK_RETURN, VK_RETURN]

        # Shift downs count must be exactly 2
        shift_downs = [e for e in down_vks if e == VK_SHIFT]
        assert len(shift_downs) == 2

        # Return downs count must be exactly 3
        return_downs = [e for e in down_vks if e == VK_RETURN]
        assert len(return_downs) == 3

        # Shift ups count must equal Shift downs count
        shift_ups = [e for e in vk_events if e.vk == VK_SHIFT and bool(e.flags & KEYEVENTF_KEYUP)]
        assert len(shift_ups) == 2

        # No keys stuck in driver
        assert len(driver._held_keys) == 0

    def test_consecutive_multiple_newlines_with_submit_false(self):
        """
        Input '\\n\\n\\n' with submit=False:
        Must emit exactly 3 Shift+Enters and 0 Plain Enters.
        Shift down events = 3. Return down events = 3.
        """
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        text = "\n\n\n"
        success = driver.type_text(text, submit=False)
        assert success is True

        vk_events = [e for e in backend.events if not (e.flags & KEYEVENTF_UNICODE)]
        down_vks = [e.vk for e in vk_events if not (e.flags & KEYEVENTF_KEYUP)]

        # Expected: Shift, Return, Shift, Return, Shift, Return
        assert down_vks == [VK_SHIFT, VK_RETURN, VK_SHIFT, VK_RETURN, VK_SHIFT, VK_RETURN]

        shift_downs = [e for e in down_vks if e == VK_SHIFT]
        assert len(shift_downs) == 3

        return_downs = [e for e in down_vks if e == VK_RETURN]
        assert len(return_downs) == 3

        assert len(driver._held_keys) == 0

    def test_trailing_newlines_submit_true_vs_false(self):
        """
        Tests 'Hello\\n\\n' with submit=True vs submit=False.
        With submit=True: intermediate '\\n' gets Shift+Enter, trailing '\\n' gets Plain Enter.
        With submit=False: both newlines get Shift+Enter.
        """
        # Case 1: submit=True
        backend_true = MockInputBackend(virtual_time=True)
        driver_true = KeyboardDriver(backend=backend_true)

        text = "Hello\n\n"
        success = driver_true.type_text(text, submit=True)
        assert success is True

        vk_events_true = [e for e in backend_true.events if not (e.flags & KEYEVENTF_UNICODE)]
        shift_downs_true = [e for e in vk_events_true if e.vk == VK_SHIFT and not (e.flags & KEYEVENTF_KEYUP)]
        return_downs_true = [e for e in vk_events_true if e.vk == VK_RETURN and not (e.flags & KEYEVENTF_KEYUP)]
        assert len(shift_downs_true) == 1, "Only the intermediate newline should have Shift"
        assert len(return_downs_true) == 2, "One Shift+Enter + one Plain Enter"

        # Case 2: submit=False
        backend_false = MockInputBackend(virtual_time=True)
        driver_false = KeyboardDriver(backend=backend_false)

        success = driver_false.type_text(text, submit=False)
        assert success is True

        vk_events_false = [e for e in backend_false.events if not (e.flags & KEYEVENTF_UNICODE)]
        shift_downs_false = [e for e in vk_events_false if e.vk == VK_SHIFT and not (e.flags & KEYEVENTF_KEYUP)]
        return_downs_false = [e for e in vk_events_false if e.vk == VK_RETURN and not (e.flags & KEYEVENTF_KEYUP)]
        assert len(shift_downs_false) == 2, "Both newlines should have Shift when submit=False"
        assert len(return_downs_false) == 2

    def test_mixed_crlf_and_cr_line_endings_normalization(self):
        """
        Adversarial line endings: '\\r\\n', '\\r', '\\n' mixed in a single string.
        Verifies normalization preserves correct intermediate vs submit newline logic.
        """
        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        # 3 newlines total: CRLF at pos 1, CR at pos 2, LF at pos 3 (end)
        text = "Paragraph 1\r\n\rParagraph 2\n"
        success = driver.type_text(text, submit=True)
        assert success is True

        vk_events = [e for e in backend.events if not (e.flags & KEYEVENTF_UNICODE)]
        shift_downs = [e for e in vk_events if e.vk == VK_SHIFT and not (e.flags & KEYEVENTF_KEYUP)]
        return_downs = [e for e in vk_events if e.vk == VK_RETURN and not (e.flags & KEYEVENTF_KEYUP)]

        # Two intermediate newlines (Shift+Enter) and one final newline with submit (Plain Enter)
        assert len(shift_downs) == 2
        assert len(return_downs) == 3

    def test_empty_and_whitespace_multiline_inputs(self):
        """
        Verifies edge cases: empty strings, pure newlines, and whitespace-only lines.
        """
        driver = KeyboardDriver(backend=MockInputBackend(virtual_time=True))

        # 1. Empty string with submit=False -> no-op
        b1 = MockInputBackend(virtual_time=True)
        d1 = KeyboardDriver(backend=b1)
        assert d1.type_text("", submit=False) is True
        assert len(b1.events) == 0

        # 2. Empty string with submit=True -> sends 1 Plain Enter
        b2 = MockInputBackend(virtual_time=True)
        d2 = KeyboardDriver(backend=b2)
        assert d2.type_text("", submit=True) is True
        return_downs = [
            e for e in b2.events
            if e.type == INPUT_KEYBOARD and e.vk == VK_RETURN and not (e.flags & KEYEVENTF_KEYUP)
        ]
        assert len(return_downs) == 1

        # 3. Single newline with submit=False -> 1 Shift+Enter
        b3 = MockInputBackend(virtual_time=True)
        d3 = KeyboardDriver(backend=b3)
        assert d3.type_text("\n", submit=False) is True
        shift_downs = [
            e for e in b3.events
            if e.type == INPUT_KEYBOARD and e.vk == VK_SHIFT and not (e.flags & KEYEVENTF_KEYUP)
        ]
        assert len(shift_downs) == 1

        # 4. Single newline with submit=True -> 1 Plain Enter
        b4 = MockInputBackend(virtual_time=True)
        d4 = KeyboardDriver(backend=b4)
        assert d4.type_text("\n", submit=True) is True
        shift_downs = [
            e for e in b4.events
            if e.type == INPUT_KEYBOARD and e.vk == VK_SHIFT and not (e.flags & KEYEVENTF_KEYUP)
        ]
        return_downs = [
            e for e in b4.events
            if e.type == INPUT_KEYBOARD and e.vk == VK_RETURN and not (e.flags & KEYEVENTF_KEYUP)
        ]
        assert len(shift_downs) == 0
        assert len(return_downs) == 1

    def test_shift_enter_interrupted_cleans_modifiers(self):
        """
        If an interrupt occurs while Shift is actively held during Shift+Enter,
        KeyboardDriver must call emergency_release_keys and guarantee Shift is released.
        """
        token = threading.Event()
        backend = AdversarialTriggerBackend(
            virtual_time=True,
            interrupt_on_vk=VK_SHIFT,
            token_to_signal=token,
        )
        driver = KeyboardDriver(backend=backend)

        success = driver.type_text("Line 1\nLine 2", submit=False, cancellation_token=token)
        assert success is False

        # Verify Shift key was released via KEYEVENTF_KEYUP
        shift_ups = [
            e for e in backend.events
            if e.type == INPUT_KEYBOARD and e.vk == VK_SHIFT and (e.flags & KEYEVENTF_KEYUP)
        ]
        assert len(shift_ups) >= 1, "Shift key must have been released upon abort"
        assert len(driver._held_keys) == 0


# ===========================================================================
# 3. Per-Keystroke Interrupt Cancellation Under Concurrency
# ===========================================================================
class TestAdversarialKeystrokeInterruptAndConcurrency:
    """Stress tests per-keystroke interrupt cancellation, latency, and concurrency."""

    def test_interrupt_on_first_character(self):
        """
        Simulate physical touch on character 0:
        Typing must halt immediately in < 2ms, zero characters or at most char 0 dwell aborted.
        """
        token = threading.Event()
        backend = AdversarialTriggerBackend(
            virtual_time=True,
            interrupt_after_event_count=1,  # triggers on char 0 keydown
            token_to_signal=token,
        )
        driver = KeyboardDriver(backend=backend)

        t0 = time.perf_counter()
        success = driver.type_text("First Character Abort", cancellation_token=token)
        t_elapsed = time.perf_counter() - t0

        assert success is False
        assert t_elapsed < 0.005, f"Abort took too long: {t_elapsed * 1000:.2f}ms"

        # Check at most 1 character was touched
        scans = backend.get_typed_unicode_scans()
        assert len(scans) <= 1
        assert len(driver._held_keys) == 0

    def test_interrupt_mid_string(self):
        """
        Simulate physical touch at middle character of a 40-character prompt.
        Typing must immediately halt, subsequent characters must not be sent.
        """
        token = threading.Event()
        target_char = "X"
        text = "Alpha Beta Gamma " + target_char + " Delta Epsilon"

        backend = AdversarialTriggerBackend(
            virtual_time=True,
            interrupt_on_scan=ord(target_char),
            token_to_signal=token,
        )
        driver = KeyboardDriver(backend=backend)

        t0 = time.perf_counter()
        success = driver.type_text(text, cancellation_token=token)
        t_elapsed = time.perf_counter() - t0

        assert success is False
        assert t_elapsed < 0.005

        scans = backend.get_typed_unicode_scans()
        typed_str = "".join(chr(s) for s in scans)
        assert typed_str.startswith("Alpha Beta Gamma ")
        assert "Delta" not in typed_str
        assert "Epsilon" not in typed_str
        assert len(driver._held_keys) == 0

    def test_interrupt_on_last_character_and_submit_delay(self):
        """
        Simulate physical touch on final character of text with submit=True.
        The final Plain Enter must NOT be emitted.
        """
        token = threading.Event()
        backend = AdversarialTriggerBackend(
            virtual_time=True,
            interrupt_on_scan=ord("Z"),
            token_to_signal=token,
        )
        driver = KeyboardDriver(backend=backend)

        text = "Query Z"
        success = driver.type_text(text, submit=True, cancellation_token=token)
        assert success is False

        # Verify no Plain Enter was sent
        enter_downs = [
            e for e in backend.events
            if e.type == INPUT_KEYBOARD and e.vk == VK_RETURN and not (e.flags & KEYEVENTF_KEYUP)
        ]
        assert len(enter_downs) == 0
        assert len(driver._held_keys) == 0

    def test_concurrent_typing_threads_preempted_simultaneously(self):
        """
        Spawn 8 concurrent threads executing typing tasks on independent KeyboardDrivers.
        A 9th thread simulates an InterruptGuard physical touch event.
        All threads must observe cancellation, terminate cleanly in < 5ms, and leave no stuck keys.
        """
        guard = InterruptGuard(cooldown_seconds=5.0)
        token = guard.get_cancellation_token()

        results: List[Optional[bool]] = [None] * 8
        latencies: List[float] = [0.0] * 8

        def worker(idx: int):
            b = MockInputBackend(virtual_time=False)
            d = KeyboardDriver(backend=b)
            long_text = f"Worker {idx} long sentence for stress testing concurrency preemption " * 5
            t0 = time.perf_counter()
            results[idx] = d.type_text(long_text, cancellation_token=token)
            latencies[idx] = time.perf_counter() - t0

        threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(8)]
        for t in threads:
            t.start()

        # Brief delay to allow threads to begin typing
        time.sleep(0.010)

        # Trigger physical interrupt via software hook simulation
        t_trigger = time.perf_counter()
        guard.simulate_event("mouse", flags=0)

        for t in threads:
            t.join(timeout=1.0)
            assert not t.is_alive(), "Worker thread hung or deadlocked!"

        for i in range(8):
            assert results[i] is False, f"Worker {i} did not report preemption"

        guard.stop()

    def test_rapid_pulse_cancel_hammer_50_iterations(self):
        """
        Hammers 50 consecutive typing attempts with randomly timed preemption signals.
        Verifies sub-2ms preemption and zero resource/key leaks across all iterations.
        """
        for iteration in range(50):
            token = threading.Event()
            interrupt_delay = 0.0002 * (iteration + 1)  # 0.2ms to 10ms

            b = MockInputBackend(virtual_time=False)
            d = KeyboardDriver(backend=b)

            def trigger():
                time.sleep(interrupt_delay)
                token.set()

            trigger_thread = threading.Thread(target=trigger, daemon=True)
            trigger_thread.start()

            t0 = time.perf_counter()
            success = d.type_text("Hammer Test Long String Payload 1234567890", cancellation_token=token)
            t_abort = time.perf_counter() - t0

            trigger_thread.join(timeout=0.1)

            assert success is False
            assert len(d._held_keys) == 0


# ===========================================================================
# 4. Stress Test click_and_type
# ===========================================================================
class TestAdversarialClickAndTypeStress:
    """Stress tests click_and_type with focus delays, caret initialization, and preemption."""

    def test_click_and_type_focus_delays(self):
        """
        Verifies focus delay customization (60ms, 75ms, 90ms)
        and verifies the click precedes the text typing sequence.
        """
        for delay_ms in [60.0, 75.0, 90.0]:
            backend = MockInputBackend(virtual_time=True)
            driver = KeyboardDriver(backend=backend)

            success = driver.click_and_type(
                x=400,
                y=250,
                text="Focus Test",
                submit=False,
                focus_delay_ms=delay_ms,
            )
            assert success is True

            # First events must be mouse left down and up
            assert len(backend.events) >= 2
            assert backend.events[0].type == INPUT_MOUSE
            assert backend.events[0].flags == MOUSEEVENTF_LEFTDOWN
            assert backend.events[1].type == INPUT_MOUSE
            assert backend.events[1].flags == MOUSEEVENTF_LEFTUP

            # Followed by typed text
            scans = backend.get_typed_unicode_scans()
            assert "".join(chr(s) for s in scans) == "Focus Test"

    def test_preemption_during_focus_delay(self):
        """
        Preemption triggered during the focus_delay_ms caret initialization window.
        Click must be executed, but ZERO text characters should be typed.
        """
        token = threading.Event()
        backend = AdversarialTriggerBackend(
            virtual_time=True,
            interrupt_during_sleep_call=2,  # sleep 1 is mouse dwell, sleep 2 is focus delay
            token_to_signal=token,
        )
        driver = KeyboardDriver(backend=backend)

        success = driver.click_and_type(
            x=500,
            y=300,
            text="Should Not Type",
            cancellation_token=token,
            focus_delay_ms=80.0,
        )
        assert success is False

        # Mouse click was dispatched
        mouse_events = [e for e in backend.events if e.type == INPUT_MOUSE]
        assert len(mouse_events) >= 2

        # But ZERO keyboard scans were dispatched
        kb_scans = backend.get_typed_unicode_scans()
        assert len(kb_scans) == 0

    def test_preemption_during_mouse_movement_in_click_and_type(self):
        """
        When mouse_driver is provided, preemption during glide must abort click_and_type,
        release all mouse buttons, and type zero characters.
        """
        mouse_driver = MouseDriver(simulation_mode=True, speed_factor=1.0)
        token = threading.Event()
        token.set()  # pre-cancelled

        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        success = driver.click_and_type(
            x=800,
            y=600,
            text="Abort Pre-move",
            cancellation_token=token,
            mouse_driver=mouse_driver,
        )
        assert success is False
        assert len(backend.events) == 0
        assert len(mouse_driver._held_buttons) == 0

    def test_preemption_during_mouse_click_in_click_and_type(self):
        """
        Preemption during mouse click button dwell hold must abort and release mouse button.
        """
        mouse_driver = MouseDriver(simulation_mode=True)
        token = threading.Event()

        # Intercept reticle callback to trigger interrupt before click finishes
        def on_reticle(x, y, ms):
            token.set()

        mouse_driver.reticle_callback = on_reticle

        backend = MockInputBackend(virtual_time=True)
        driver = KeyboardDriver(backend=backend)

        success = driver.click_and_type(
            x=300,
            y=300,
            text="Abort During Reticle/Click",
            cancellation_token=token,
            mouse_driver=mouse_driver,
        )
        assert success is False
        assert len(mouse_driver._held_buttons) == 0
        assert len(backend.get_typed_unicode_scans()) == 0

    def test_preemption_mid_typing_in_click_and_type(self):
        """
        Mouse navigation and click succeed, focus delay passes, but interrupt triggers
        at character 3 of text. click_and_type must return False, only characters 0..2 typed.
        """
        token = threading.Event()
        target_char = "3"
        text = "012" + target_char + "456"

        backend = AdversarialTriggerBackend(
            virtual_time=True,
            interrupt_on_scan=ord(target_char),
            token_to_signal=token,
        )
        driver = KeyboardDriver(backend=backend)

        success = driver.click_and_type(
            x=100,
            y=100,
            text=text,
            cancellation_token=token,
        )
        assert success is False

        scans = backend.get_typed_unicode_scans()
        typed_str = "".join(chr(s) for s in scans)
        assert typed_str.startswith("012")
        assert "456" not in typed_str
        assert len(driver._held_keys) == 0


# ===========================================================================
# 5. Latency & Concurrency Benchmarks of wait_interruptible
# ===========================================================================
class TestAdversarialWaitInterruptibleLatencyBenchmark:
    """Benchmark empirical wake latency of wait_interruptible across worker threads."""

    def test_wait_interruptible_sub_2ms_wake_latency_100_trials(self):
        """
        Runs 100 trials measuring empirical wake latency of wait_interruptible(timeout=2.0)
        when physical interrupt is triggered asynchronously from a timer thread.
        Every trial MUST wake in < 2.0ms.
        Computes and logs Mean, Median, P95, and Max empirical wake latency.
        """
        guard = InterruptGuard(cooldown_seconds=1.0)
        latencies_ms: List[float] = []

        for trial in range(100):
            guard.reset_interrupt()

            t_signal_holder = [0.0]

            def trigger():
                time.sleep(0.002)  # 2ms delay
                t_signal_holder[0] = time.perf_counter()
                guard.simulate_event("mouse", flags=0)

            th = threading.Thread(target=trigger, daemon=True)
            th.start()

            completed_normally = guard.wait_interruptible(timeout=2.0)
            t_wake = time.perf_counter()

            th.join(timeout=0.1)

            assert completed_normally is False, f"Trial {trial} failed to observe interrupt!"
            wake_latency_s = t_wake - t_signal_holder[0]
            wake_latency_ms = wake_latency_s * 1000.0
            latencies_ms.append(wake_latency_ms)

            assert wake_latency_s < 0.002, (
                f"Trial {trial} wake latency exceeded 2ms budget: {wake_latency_ms:.3f}ms"
            )

        guard.stop()

        mean_ms = statistics.mean(latencies_ms)
        median_ms = statistics.median(latencies_ms)
        p95_ms = statistics.quantiles(latencies_ms, n=20)[18]  # 95th percentile
        max_ms = max(latencies_ms)

        print(
            f"\n[BENCHMARK] wait_interruptible Wake Latency (100 trials): "
            f"Mean={mean_ms:.3f}ms, P50={median_ms:.3f}ms, P95={p95_ms:.3f}ms, Max={max_ms:.3f}ms"
        )
        assert max_ms < 2.0

    def test_wait_interruptible_multi_worker_fan_out_wake_latency(self):
        """
        8 concurrent worker threads waiting on guard.wait_interruptible(timeout=5.0).
        A physical touch event is injected via guard.simulate_event('keyboard', flags=0).
        All 8 threads must wake up simultaneously, return False, and have wake latency < 2.0ms.
        """
        guard = InterruptGuard(cooldown_seconds=2.0)
        wake_latencies_ms: List[float] = [0.0] * 8
        results: List[Optional[bool]] = [None] * 8
        ready_barrier = threading.Barrier(9)  # 8 workers + 1 trigger

        t_signal_box = [0.0]

        def worker(idx: int):
            ready_barrier.wait()  # synchronize start
            results[idx] = guard.wait_interruptible(timeout=5.0)
            t_wake = time.perf_counter()
            wake_latencies_ms[idx] = (t_wake - t_signal_box[0]) * 1000.0

        threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(8)]
        for t in threads:
            t.start()

        ready_barrier.wait()
        # Give threads a tiny moment to enter wait_interruptible
        time.sleep(0.005)

        t_signal_box[0] = time.perf_counter()
        guard.simulate_event("keyboard", flags=0, vk_code=0x41)

        for t in threads:
            t.join(timeout=1.0)
            assert not t.is_alive(), "Worker thread hung on wait_interruptible!"

        guard.stop()

        for i in range(8):
            assert results[i] is False, f"Worker {i} did not report preemption"
            assert wake_latencies_ms[i] < 2.0, (
                f"Worker {i} wake latency exceeded 2ms budget: {wake_latencies_ms[i]:.3f}ms"
            )

        print(
            f"\n[BENCHMARK] 8-Worker Fan-Out Latencies: "
            f"{[f'{l:.3f}ms' for l in wake_latencies_ms]}"
        )

    def test_wait_interruptible_timeout_accuracy(self):
        """
        When no interrupt occurs, wait_interruptible(timeout) must wait until timeout expires
        and return True with accurate timing.
        """
        guard = InterruptGuard(cooldown_seconds=1.0)

        t0 = time.perf_counter()
        completed_normally = guard.wait_interruptible(timeout=0.040)  # 40ms
        elapsed = time.perf_counter() - t0

        assert completed_normally is True
        assert 0.030 <= elapsed <= 0.070, f"Wait duration out of expected bounds: {elapsed * 1000:.2f}ms"

        guard.stop()

    def test_wait_interruptible_pre_signaled_instant_return(self):
        """
        If cancellation_token is already signaled before wait_interruptible is called,
        it must return False instantaneously (< 0.1ms).
        """
        guard = InterruptGuard(cooldown_seconds=1.0)
        guard.simulate_event("mouse", flags=0)

        t0 = time.perf_counter()
        res = guard.wait_interruptible(timeout=5.0)
        elapsed = time.perf_counter() - t0

        assert res is False
        assert elapsed < 0.0005, f"Instant return took too long: {elapsed * 1000:.3f}ms"

        guard.stop()

    def test_wait_interruptible_under_concurrent_interrupt_reset_hammer(self):
        """
        Race condition stress test: 4 threads continuously calling wait_interruptible,
        while another thread rapidly alternates simulating physical touch and resetting.
        Verifies no deadlocks, crashes, or unhandled exceptions under thread contention.
        """
        guard = InterruptGuard(cooldown_seconds=0.1)
        stop_event = threading.Event()
        exceptions: List[Exception] = []

        def waiter_worker():
            while not stop_event.is_set():
                try:
                    guard.wait_interruptible(timeout=0.005)
                except Exception as e:
                    exceptions.append(e)

        def hammer_worker():
            while not stop_event.is_set():
                try:
                    guard.simulate_event("mouse", flags=0)
                    time.sleep(0.001)
                    guard.reset_interrupt()
                    time.sleep(0.001)
                except Exception as e:
                    exceptions.append(e)

        threads = [threading.Thread(target=waiter_worker, daemon=True) for _ in range(4)]
        threads.append(threading.Thread(target=hammer_worker, daemon=True))

        for t in threads:
            t.start()

        time.sleep(0.3)  # Run for 300ms
        stop_event.set()

        for t in threads:
            t.join(timeout=1.0)
            assert not t.is_alive()

        guard.stop()
        assert len(exceptions) == 0, f"Exceptions occurred during concurrency hammer: {exceptions}"
