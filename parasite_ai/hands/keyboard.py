"""
ParasiteAI - Physical Unicode Keyboard Driver.
Injects keystrokes via Win32 SendInput using KEYEVENTF_UNICODE (0x0004),
splits astral plane emojis into UTF-16 surrogate pairs, enforces Shift+Enter
multiline safety, applies human cadence jitter, and guarantees sub-2ms abort
latency via per-keystroke interrupt verification.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Protocol, Set, Tuple

from parasite_ai.config import KeyboardConfig


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Win32 Constants
# ---------------------------------------------------------------------------
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000

# Virtual Key Codes
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt key
VK_PAUSE = 0x13
VK_CAPITAL = 0x14  # Caps Lock
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_P = 0x50

VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_PRIOR = 0x21
VK_NEXT = 0x22
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_INSERT = 0x2D
VK_DELETE = 0x2E

# System Metrics
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# Hook Injected Flags
LLMHF_INJECTED = 0x00000001
LLKHF_INJECTED = 0x00000010
LLKHF_ALTDOWN = 0x00000020
LLKHF_UP = 0x00000080


# ---------------------------------------------------------------------------
# Ctypes Struct Definitions (Exact 40-byte x64 Alignment)
# ---------------------------------------------------------------------------
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    """
    Win32 tagINPUT struct.
    On 64-bit Windows:
    Offset 0: type (DWORD, 4 bytes)
    Offset 4: [4 bytes compiler padding for union alignment]
    Offset 8: u (INPUT_UNION, 32 bytes)
    Total size: 40 bytes.
    """
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    ]

    @property
    def ki(self) -> KEYBDINPUT:
        return self.u.ki

    @property
    def mi(self) -> MOUSEINPUT:
        return self.u.mi

    @property
    def hi(self) -> HARDWAREINPUT:
        return self.u.hi


assert ctypes.sizeof(INPUT) == 40, f"INPUT size must be 40 bytes, got {ctypes.sizeof(INPUT)}"
assert INPUT.u.offset == 8, f"INPUT.u offset must be 8 bytes, got {INPUT.u.offset}"
assert ctypes.sizeof(KEYBDINPUT) == 24, f"KEYBDINPUT size must be 24 bytes, got {ctypes.sizeof(KEYBDINPUT)}"
assert ctypes.sizeof(MOUSEINPUT) == 32, f"MOUSEINPUT size must be 32 bytes, got {ctypes.sizeof(MOUSEINPUT)}"


# ---------------------------------------------------------------------------
# Backend Abstraction: IInputBackend, Win32InputBackend, MockInputBackend
# ---------------------------------------------------------------------------
class CapturedInputEvent:
    """Represents a recorded hardware input packet for test verification."""

    def __init__(
        self,
        event_type: int,
        vk: int = 0,
        scan: int = 0,
        flags: int = 0,
        dx: int = 0,
        dy: int = 0,
    ):
        self.type = event_type
        self.vk = vk
        self.scan = scan
        self.flags = flags
        self.dx = dx
        self.dy = dy
        self.timestamp = time.perf_counter()

    def __repr__(self) -> str:
        if self.type == INPUT_KEYBOARD:
            return f"<KeyEvent vk=0x{self.vk:02X} scan=0x{self.scan:04X} flags=0x{self.flags:04X}>"
        elif self.type == INPUT_MOUSE:
            return f"<MouseEvent flags=0x{self.flags:04X} dx={self.dx} dy={self.dy}>"
        return f"<InputEvent type={self.type}>"


class IInputBackend(Protocol):
    """Protocol for physical or simulated Windows input dispatch."""

    def send_inputs(self, inputs: List[INPUT]) -> int:
        """Dispatches an array of INPUT structures."""
        ...

    def sleep_interruptible(
        self,
        duration_s: float,
        cancellation_token: Optional[threading.Event],
    ) -> bool:
        """Sleeps for duration_s or until cancellation_token is set. Returns True if interrupted."""
        ...

    def get_cursor_pos(self) -> Tuple[int, int]:
        """Returns current cursor (x, y)."""
        ...

    def get_screen_metrics(self) -> Tuple[int, int, int, int, int, int]:
        """Returns (cx, cy, vx, vy, vcx, vcy)."""
        ...


class Win32InputBackend:
    """Direct Win32 API implementation using SendInput and high-resolution timer."""

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
        self._user32.SendInput.restype = wintypes.UINT

        self._user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        self._user32.GetCursorPos.restype = wintypes.BOOL

    def send_inputs(self, inputs: List[INPUT]) -> int:
        n = len(inputs)
        if n == 0:
            return 0
        arr = (INPUT * n)(*inputs)
        return self._user32.SendInput(n, arr, ctypes.sizeof(INPUT))

    def sleep_interruptible(
        self,
        duration_s: float,
        cancellation_token: Optional[threading.Event],
    ) -> bool:
        if cancellation_token is None:
            time.sleep(duration_s)
            return False
        return cancellation_token.wait(timeout=duration_s)

    def get_cursor_pos(self) -> Tuple[int, int]:
        pt = wintypes.POINT()
        if self._user32.GetCursorPos(ctypes.byref(pt)):
            return (pt.x, pt.y)
        return (0, 0)

    def get_screen_metrics(self) -> Tuple[int, int, int, int, int, int]:
        cx = self._user32.GetSystemMetrics(SM_CXSCREEN)
        cy = self._user32.GetSystemMetrics(SM_CYSCREEN)
        vx = self._user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = self._user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vcx = self._user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        vcy = self._user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        return (cx, cy, vx, vy, vcx, vcy)


class MockInputBackend:
    """In-memory recording backend for deterministic unit and stress tests."""

    def __init__(
        self,
        virtual_time: bool = True,
        screen_metrics: Tuple[int, int, int, int, int, int] = (1920, 1080, 0, 0, 1920, 1080),
    ):
        self.events: List[CapturedInputEvent] = []
        self.virtual_time = virtual_time
        self.screen_metrics = screen_metrics
        self.cursor_pos = (960, 540)
        self.interrupt_on_char: Optional[str] = None
        self.interrupt_on_count: Optional[int] = None
        self._bound_token: Optional[threading.Event] = None

    def send_inputs(self, inputs: List[INPUT]) -> int:
        for inp in inputs:
            if inp.type == INPUT_KEYBOARD:
                ev = CapturedInputEvent(
                    INPUT_KEYBOARD,
                    vk=inp.u.ki.wVk,
                    scan=inp.u.ki.wScan,
                    flags=inp.u.ki.dwFlags,
                )
                self.events.append(ev)

                # Check triggered interrupts for tests
                if self.interrupt_on_count and len(self.events) >= self.interrupt_on_count:
                    if self._bound_token:
                        self._bound_token.set()

                if self.interrupt_on_char and inp.u.ki.wScan == ord(self.interrupt_on_char):
                    if self._bound_token:
                        self._bound_token.set()

            elif inp.type == INPUT_MOUSE:
                ev = CapturedInputEvent(
                    INPUT_MOUSE,
                    flags=inp.u.mi.dwFlags,
                    dx=inp.u.mi.dx,
                    dy=inp.u.mi.dy,
                )
                self.events.append(ev)
        return len(inputs)

    def sleep_interruptible(
        self,
        duration_s: float,
        cancellation_token: Optional[threading.Event],
    ) -> bool:
        self._bound_token = cancellation_token
        if cancellation_token and cancellation_token.is_set():
            return True

        if not self.virtual_time:
            if cancellation_token:
                return cancellation_token.wait(timeout=duration_s)
            time.sleep(duration_s)
            return False

        # In virtual time, simulate instant passage unless token triggers
        return bool(cancellation_token and cancellation_token.is_set())

    def get_cursor_pos(self) -> Tuple[int, int]:
        return self.cursor_pos

    def set_cursor_pos(self, x: int, y: int) -> None:
        self.cursor_pos = (x, y)

    def get_screen_metrics(self) -> Tuple[int, int, int, int, int, int]:
        return self.screen_metrics

    # Test Inspection Helpers
    def get_typed_unicode_scans(self) -> List[int]:
        """Returns sequence of wScan values for KEYEVENTF_UNICODE down events."""
        return [
            e.scan
            for e in self.events
            if e.type == INPUT_KEYBOARD
            and (e.flags & KEYEVENTF_UNICODE)
            and not (e.flags & KEYEVENTF_KEYUP)
        ]

    def get_vk_down_events(self) -> List[int]:
        """Returns sequence of wVk values for virtual-key down events."""
        return [
            e.vk
            for e in self.events
            if e.type == INPUT_KEYBOARD
            and not (e.flags & KEYEVENTF_UNICODE)
            and not (e.flags & KEYEVENTF_KEYUP)
        ]

    def clear(self) -> None:
        self.events.clear()


# ---------------------------------------------------------------------------
# KeyboardDriver
# ---------------------------------------------------------------------------
class KeyboardDriver:
    """
    Physical Unicode Keyboard Driver for ParasiteAI.
    Injects keystrokes via Win32 SendInput using KEYEVENTF_UNICODE (0x0004),
    splits astral plane emojis into UTF-16 surrogate pairs, enforces Shift+Enter
    multiline safety, applies human cadence jitter, and guarantees sub-2ms abort
    latency via per-keystroke interrupt verification.
    """

    def __init__(
        self,
        config: Optional[KeyboardConfig] = None,
        backend: Optional[IInputBackend] = None,
    ):
        self.config = config or KeyboardConfig()
        self.backend = backend or Win32InputBackend()
        self._held_keys: Set[int] = set()

    @staticmethod
    def decompose_utf16(char: str) -> List[int]:
        """
        Decomposes a single character into 16-bit UTF-16 code unit scan codes.
        BMP characters return [ord(char)]. Astral characters (>0xFFFF) return [W1, W2].
        """
        cp = ord(char)
        if cp <= 0xFFFF:
            return [cp]
        u_prime = cp - 0x10000
        w1 = 0xD800 + (u_prime >> 10)
        w2 = 0xDC00 + (u_prime & 0x3FF)
        return [w1, w2]

    def type_text(
        self,
        text: str,
        submit: bool = False,
        cancellation_token: Optional[threading.Event] = None,
        cadence_jitter_ms: Optional[Tuple[int, int]] = None,
    ) -> bool:
        """
        Types Unicode text with layout independence, cadence jitter, Shift+Enter
        for intermediate newlines, and per-keystroke interrupt checks.

        Returns:
            True if text typing completed fully.
            False if aborted mid-typing by cancellation_token.
        """
        if not text and not submit:
            return True

        if cancellation_token and cancellation_token.is_set():
            return False

        # Normalize CRLF and CR to plain LF
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        jitter_bounds = cadence_jitter_ms or self.config.cadence_jitter_ms

        total_chars = len(normalized)
        for i, char in enumerate(normalized):
            if cancellation_token and cancellation_token.is_set():
                self.emergency_release_keys()
                return False

            is_final_char = (i == total_chars - 1)

            if char == "\n":
                if is_final_char and submit:
                    # Final newline with submit -> plain Enter
                    if not self._send_plain_enter(cancellation_token):
                        return False
                else:
                    # Intermediate newline -> Shift + Enter to avoid premature web chat submit
                    if not self._send_shift_enter(cancellation_token):
                        return False
            else:
                # Direct Unicode character injection (handles astral surrogate pairs)
                if not self._send_unicode_char(char, cancellation_token):
                    return False

            # Cadence jitter pause between keystrokes
            if not is_final_char:
                pause_s = self._calculate_inter_key_delay(char, jitter_bounds)
                if self.backend.sleep_interruptible(pause_s, cancellation_token):
                    self.emergency_release_keys()
                    return False

        # If submit requested but text didn't end with a newline, send final Enter
        if submit and not normalized.endswith("\n"):
            pause_s = random.uniform(0.06, 0.12)
            if self.backend.sleep_interruptible(pause_s, cancellation_token):
                self.emergency_release_keys()
                return False
            if not self._send_plain_enter(cancellation_token):
                return False

        return True

    def click_and_type(
        self,
        x: int,
        y: int,
        text: str,
        submit: bool = False,
        cancellation_token: Optional[threading.Event] = None,
        mouse_driver: Optional[Any] = None,
        focus_delay_ms: float = 75.0,
    ) -> bool:
        """
        Atomic focus and type sequence:
        1. Glides cursor to (x, y)
        2. Executes left click
        3. Waits focus_delay_ms (60-90ms) for caret initialization
        4. Types text with per-key interrupt checking
        """
        if cancellation_token and cancellation_token.is_set():
            return False

        # Step 1 & 2: Mouse navigation and click
        if mouse_driver is not None:
            if not mouse_driver.move_to(x, y, cancellation_token=cancellation_token):
                return False
            if not mouse_driver.click(x, y, button="left", cancellation_token=cancellation_token):
                return False
        else:
            # Standalone coordinate click via backend
            if not self._raw_mouse_click(x, y, cancellation_token):
                return False

        # Step 3: Focus Caret Initialization Wait (60-90ms)
        if self.backend.sleep_interruptible(focus_delay_ms / 1000.0, cancellation_token):
            return False

        # Step 4: Type Text
        return self.type_text(text, submit=submit, cancellation_token=cancellation_token)

    def hotkey(
        self,
        *keys: str,
        cancellation_token: Optional[threading.Event] = None,
    ) -> bool:
        """
        Executes a physical key combination (e.g. hotkey('ctrl', 'c')).
        """
        if cancellation_token and cancellation_token.is_set():
            return False

        vk_map = {
            "ctrl": VK_CONTROL,
            "control": VK_CONTROL,
            "alt": VK_MENU,
            "menu": VK_MENU,
            "shift": VK_SHIFT,
            "win": VK_LWIN,
            "windows": VK_LWIN,
            "lwin": VK_LWIN,
            "rwin": VK_RWIN,
            "super": VK_LWIN,
            "meta": VK_LWIN,
            "enter": VK_RETURN,
            "return": VK_RETURN,
            "esc": VK_ESCAPE,
            "escape": VK_ESCAPE,
            "tab": VK_TAB,
            "backspace": VK_BACK,
            "space": VK_SPACE,
            "delete": VK_DELETE,
            "del": VK_DELETE,
            "insert": VK_INSERT,
            "ins": VK_INSERT,
            "home": VK_HOME,
            "end": VK_END,
            "pageup": VK_PRIOR,
            "pgup": VK_PRIOR,
            "pagedown": VK_NEXT,
            "pgdn": VK_NEXT,
            "left": VK_LEFT,
            "up": VK_UP,
            "right": VK_RIGHT,
            "down": VK_DOWN,
            "p": VK_P,
            **{f"f{i}": 0x6F + i for i in range(1, 13)},
        }

        vks: List[int] = []
        for k in keys:
            k_lower = k.lower()
            if k_lower in vk_map:
                vks.append(vk_map[k_lower])
            elif len(k) == 1:
                vks.append(ord(k.upper()))
            else:
                raise ValueError(f"Unknown hotkey name: '{k}'")

        # Key Downs in order
        for vk in vks:
            if cancellation_token and cancellation_token.is_set():
                self.emergency_release_keys()
                return False
            self._send_vk_event(vk, down=True)
            self._held_keys.add(vk)
            if self.backend.sleep_interruptible(0.015, cancellation_token):
                self.emergency_release_keys()
                return False

        # Brief hold
        if self.backend.sleep_interruptible(0.030, cancellation_token):
            self.emergency_release_keys()
            return False

        # Key Ups in reverse order
        for vk in reversed(vks):
            self._send_vk_event(vk, down=False)
            self._held_keys.discard(vk)
            if self.backend.sleep_interruptible(0.010, cancellation_token):
                self.emergency_release_keys()
                return False

        return True

    def emergency_release_keys(self) -> None:
        """
        Releases all currently tracked held keys and vital modifier keys.
        Guarantees no stuck-key or stuck-modifier state.
        """
        keys_to_release = set(self._held_keys) | {
            VK_SHIFT,
            VK_LSHIFT,
            VK_RSHIFT,
            VK_CONTROL,
            VK_LCONTROL,
            VK_RCONTROL,
            VK_MENU,
            VK_LMENU,
            VK_RMENU,
        }
        for vk in keys_to_release:
            self._send_vk_event(vk, down=False)
        self._held_keys.clear()

    # -----------------------------------------------------------------------
    # Internal Keystroke Dispatch Helpers
    # -----------------------------------------------------------------------
    def _send_unicode_char(
        self,
        char: str,
        cancellation_token: Optional[threading.Event],
    ) -> bool:
        code_units = self.decompose_utf16(char)
        dwell_s = random.uniform(0.012, 0.024)

        for w in code_units:
            if cancellation_token and cancellation_token.is_set():
                self.emergency_release_keys()
                return False

            # Key Down (KEYEVENTF_UNICODE = 0x0004)
            inp_down = INPUT(type=INPUT_KEYBOARD)
            inp_down.u.ki.wVk = 0
            inp_down.u.ki.wScan = w
            inp_down.u.ki.dwFlags = KEYEVENTF_UNICODE
            inp_down.u.ki.dwExtraInfo = 0
            self.backend.send_inputs([inp_down])

            # Interruptible dwell hold
            if self.backend.sleep_interruptible(dwell_s, cancellation_token):
                # Send key up immediately before aborting to avoid stuck character
                inp_up = INPUT(type=INPUT_KEYBOARD)
                inp_up.u.ki.wVk = 0
                inp_up.u.ki.wScan = w
                inp_up.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
                inp_up.u.ki.dwExtraInfo = 0
                self.backend.send_inputs([inp_up])
                self.emergency_release_keys()
                return False

            # Key Up (KEYEVENTF_UNICODE | KEYEVENTF_KEYUP = 0x0006)
            inp_up = INPUT(type=INPUT_KEYBOARD)
            inp_up.u.ki.wVk = 0
            inp_up.u.ki.wScan = w
            inp_up.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            inp_up.u.ki.dwExtraInfo = 0
            self.backend.send_inputs([inp_up])

        return True

    def _send_shift_enter(self, cancellation_token: Optional[threading.Event]) -> bool:
        """Sends Shift down -> Enter down/up -> Shift up."""
        if cancellation_token and cancellation_token.is_set():
            return False

        # Shift Down
        self._send_vk_event(VK_SHIFT, down=True)
        self._held_keys.add(VK_SHIFT)

        if self.backend.sleep_interruptible(0.015, cancellation_token):
            self.emergency_release_keys()
            return False

        # Enter Down & Up
        self._send_vk_event(VK_RETURN, down=True)
        if self.backend.sleep_interruptible(0.015, cancellation_token):
            self.emergency_release_keys()
            return False
        self._send_vk_event(VK_RETURN, down=False)

        if self.backend.sleep_interruptible(0.015, cancellation_token):
            self.emergency_release_keys()
            return False

        # Shift Up
        self._send_vk_event(VK_SHIFT, down=False)
        self._held_keys.discard(VK_SHIFT)
        return True

    def _send_plain_enter(self, cancellation_token: Optional[threading.Event]) -> bool:
        """Sends plain VK_RETURN down then up."""
        if cancellation_token and cancellation_token.is_set():
            return False

        self._send_vk_event(VK_RETURN, down=True)
        if self.backend.sleep_interruptible(0.020, cancellation_token):
            self._send_vk_event(VK_RETURN, down=False)
            self.emergency_release_keys()
            return False
        self._send_vk_event(VK_RETURN, down=False)
        return True

    def _send_vk_event(self, vk: int, down: bool) -> None:
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.u.ki.wVk = vk
        inp.u.ki.wScan = 0
        inp.u.ki.dwFlags = 0 if down else KEYEVENTF_KEYUP
        inp.u.ki.dwExtraInfo = 0
        self.backend.send_inputs([inp])

    def _calculate_inter_key_delay(self, char: str, bounds: Tuple[int, int]) -> float:
        min_ms, max_ms = bounds

        # Syntactic Pauses
        if char in {'.', '?', '!'}:
            return random.uniform(0.150, 0.300)
        if char in {',', ';', ':', '-', '(', ')'}:
            return random.uniform(0.080, 0.150)
        if char == ' ':
            # Cognitive micro-hesitation
            if random.random() < self.config.micro_pause_probability:
                return random.uniform(0.200, 0.500)

        # Log-Normal Cadence Jitter
        val_ms = random.lognormvariate(3.8, 0.35)
        clamped_ms = max(min_ms, min(max_ms, val_ms))
        return clamped_ms / 1000.0

    def _raw_mouse_click(self, x: int, y: int, cancellation_token: Optional[threading.Event]) -> bool:
        """Direct mouse down and up at current position."""
        if cancellation_token and cancellation_token.is_set():
            return False

        inp_down = INPUT(type=INPUT_MOUSE)
        inp_down.u.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
        self.backend.send_inputs([inp_down])

        if self.backend.sleep_interruptible(0.040, cancellation_token):
            inp_up = INPUT(type=INPUT_MOUSE)
            inp_up.u.mi.dwFlags = MOUSEEVENTF_LEFTUP
            self.backend.send_inputs([inp_up])
            return False

        inp_up = INPUT(type=INPUT_MOUSE)
        inp_up.u.mi.dwFlags = MOUSEEVENTF_LEFTUP
        self.backend.send_inputs([inp_up])
        return True
