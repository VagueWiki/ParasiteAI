# Milestone M2 Technical Implementation Plan: Unicode Keyboard Driver & Global Panic Abort Subsystem

**Author:** teamwork_explorer_m2_3  
**Target Subsystems:**
- `parasite_ai.hands.keyboard` (`parasite_ai/hands/keyboard.py`)
- `parasite_ai.safety.panic` (`parasite_ai/safety/panic.py`)
- `tests.test_keyboard_driver` (`tests/test_keyboard_driver.py`)
- `tests.test_panic` (`tests/test_panic.py`)

---

## 1. Executive Summary & Architectural Decomposition

ParasiteAI requires direct, human-like physical keyboard interaction combined with an instant, multi-layered fail-safe panic abort system.

### Core Challenges Addressed:
1. **64-bit Win32 ABI Alignment:** Win32 `INPUT` structures on x64 require exact 40-byte total sizing with an 8-byte union offset. Any mismatch produces silent `ERROR_INVALID_PARAMETER (87)` failures or heap corruption.
2. **Layout-Independent Unicode Injection:** Sending virtual key codes (`VK_A`) breaks across international keyboard layouts. Using `KEYEVENTF_UNICODE (0x0004)` with `wScan = ord(char)` ensures character fidelity across AZERTY, QWERTZ, Cyrillic, and CJK systems.
3. **Astral Plane Unicode (Emojis & Symbols):** Characters with code points $> 0xFFFF$ (e.g. 🤖, 🌍, 🚀, 🔥) cannot fit in a 16-bit scan code and must be split into UTF-16 surrogate pairs ($W_1, W_2$).
4. **Multiline Web Chat Safety:** Pressing plain `VK_RETURN` in web chat applications (ChatGPT, Claude, Gemini, Slack) immediately submits incomplete prompts. Intermediate newlines must be converted to `Shift + Enter` (`VK_SHIFT` Down $\to$ `VK_RETURN` Down/Up $\to$ `VK_SHIFT` Up).
5. **Sub-2ms Interrupt Abort:** Before and after every single keystroke, the active cancellation token is inspected. If physical user touch or panic is detected, typing aborts in $< 0.2$ms and resets hardware state.
6. **Multi-Layered Global Panic Triggers:** An emergency stop system supporting `Esc` (during driving/offloading), `Ctrl + Alt + P` and `Ctrl + Alt + Backspace` (system-wide), and screen corner slam ($\le 4$px from any monitor corner).
7. **Emergency Hardware State Neutralization:** When panic fires, all held mouse buttons and modifier keys (`Shift`, `Ctrl`, `Alt`) are explicitly released to prevent stuck-key states.
8. **Deterministic CI Simulation:** Headless CI test suites execute via an abstracted backend (`IInputBackend` / `MockInputBackend`) verifying events and timings without touching real user hardware.

---

## 2. Win32 `SendInput` ctypes Specifications (64-Bit ABI)

### 2.1 Struct Memory Layout Verification

On 64-bit Windows (x64 / AMD64), pointer and `ULONG_PTR` members are 8 bytes, aligning the union within `tagINPUT` to offset 8.

```
Offset 0:  [ DWORD type (4 bytes) ]
Offset 4:  [ Alignment Padding (4 bytes) ]
Offset 8:  [ UNION (32 bytes) ]
             ├── MOUSEINPUT    (32 bytes)
             ├── KEYBDINPUT    (24 bytes + 8 bytes union slack)
             └── HARDWAREINPUT (8 bytes + 24 bytes union slack)
Total Size: 40 bytes
```

### 2.2 Verbatim ctypes Implementation

```python
import ctypes
from ctypes import wintypes
from typing import Optional, Protocol, Tuple, List, Set, Callable
import struct
import math
import random
import time
import threading

# ---------------------------------------------------------------------------
# Win32 Constants
# ---------------------------------------------------------------------------
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002
KEYEVENTF_UNICODE     = 0x0004
KEYEVENTF_SCANCODE    = 0x0008

MOUSEEVENTF_MOVE      = 0x0001
MOUSEEVENTF_LEFTDOWN  = 0x0002
MOUSEEVENTF_LEFTUP    = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP   = 0x0010
MOUSEEVENTF_MIDDLEDOWN= 0x0020
MOUSEEVENTF_MIDDLEUP  = 0x0040
MOUSEEVENTF_ABSOLUTE  = 0x8000

# Virtual Key Codes
VK_BACK    = 0x08
VK_TAB     = 0x09
VK_RETURN  = 0x0D
VK_SHIFT   = 0x10
VK_CONTROL = 0x11
VK_MENU    = 0x12  # Alt key
VK_PAUSE   = 0x13
VK_CAPITAL = 0x14  # Caps Lock
VK_ESCAPE  = 0x1B
VK_SPACE   = 0x20
VK_P       = 0x50

VK_LSHIFT   = 0xA0
VK_RSHIFT   = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU    = 0xA4
VK_RMENU    = 0xA5

# System Metrics
SM_CXSCREEN        = 0
SM_CYSCREEN        = 1
SM_XVIRTUALSCREEN  = 76
SM_YVIRTUALSCREEN  = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# Hook Injected Flags
LLMHF_INJECTED = 0x00000001
LLKHF_INJECTED = 0x00000010
LLKHF_ALTDOWN  = 0x00000020
LLKHF_UP       = 0x00000080


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
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    ]

assert ctypes.sizeof(INPUT) == 40, f"INPUT size must be 40 bytes, got {ctypes.sizeof(INPUT)}"
assert INPUT.u.offset == 8, f"INPUT.u offset must be 8 bytes, got {INPUT.u.offset}"
assert ctypes.sizeof(KEYBDINPUT) == 24, f"KEYBDINPUT size must be 24 bytes, got {ctypes.sizeof(KEYBDINPUT)}"
assert ctypes.sizeof(MOUSEINPUT) == 32, f"MOUSEINPUT size must be 32 bytes, got {ctypes.sizeof(MOUSEINPUT)}"
```

---

## 3. Mathematical Specifications

### 3.1 Astral Plane UTF-16 Surrogate Pair Decomposition

For any Unicode code point $C$:
- **BMP Range ($C \le 0xFFFF$):**
  A single 16-bit code unit is emitted:
  $$\text{code\_units} = [C]$$
- **Astral Plane Range ($C > 0xFFFF$ and $C \le 0x10FFFF$):**
  Decomposed into High Surrogate ($W_1$) and Low Surrogate ($W_2$):
  $$U' = C - 0x10000 \quad (0 \le U' \le 0xFFFFF)$$
  $$W_1 = 0xD800 + (U' \gg 10) \quad (0xD800 \le W_1 \le 0xDBFF)$$
  $$W_2 = 0xDC00 + (U' \ \& \ 0x3FF) \quad (0xDC00 \le W_2 \le 0xDFFF)$$
  $$\text{code\_units} = [W_1, W_2]$$

Each code unit $W$ requires two consecutive `INPUT` events:
1. `KEYEVENTF_UNICODE (0x0004)`: Key Down (`wVk = 0, wScan = W`)
2. `KEYEVENTF_UNICODE | KEYEVENTF_KEYUP (0x0006)`: Key Up (`wVk = 0, wScan = W`)

For an astral emoji (e.g. 🤖 `U+1F916` $\to W_1 = 0xD83E, W_2 = 0xDD16$), the driver sends:
- $W_1$ Down $\to W_1$ Up $\to W_2$ Down $\to W_2$ Up (4 `SendInput` packets total).

### 3.2 Human Cadence Jitter Model

Human typing speed is characterized by log-normal inter-key distributions punctuated by syntactic pauses.

1. **Inter-Key Delay Distribution:**
   $$t_{\text{inter}} \sim \text{LogNormal}(\mu=3.8, \sigma=0.35) \text{ ms}$$
   Clamped to $[T_{\min}, T_{\max}] = [25\text{ ms}, 75\text{ ms}]$ (or derived from configured `KeyboardConfig.cadence_jitter_ms`).
2. **Punctuation Pauses:**
   After characters in $\{ ',', ';', ':', '-', '\u2014', '(', ')' \}$:
   $$t_{\text{pause}} = t_{\text{inter}} + \text{Uniform}(80\text{ ms}, 150\text{ ms})$$
3. **Sentence & Paragraph Pauses:**
   After characters in $\{ '.', '?', '!', '\n' \}$:
   $$t_{\text{pause}} = t_{\text{inter}} + \text{Uniform}(150\text{ ms}, 300\text{ ms})$$
4. **Cognitive Micro-Hesitation:**
   With probability $p = 0.04$ following a space character `' '`:
   $$t_{\text{pause}} = \text{Uniform}(200\text{ ms}, 600\text{ ms})$$
5. **Key Dwell Time (Hold Duration):**
   Between Key Down and Key Up:
   $$t_{\text{dwell}} \sim \text{Uniform}(12\text{ ms}, 25\text{ ms})$$
6. **Interruptible Sleep Mechanics:**
   Every pause and dwell interval uses `cancellation_token.wait(timeout=t)` rather than blocking `time.sleep(t)`. If the token is signaled, the wait terminates in $< 0.1$ms.

### 3.3 Screen Corner Slam Detection Geometry

For a desktop with primary resolution $(W_p, H_p)$ and virtual desktop bounding box $(X_v, Y_v, W_v, H_v)$, given cursor coordinates $(x, y)$ and corner slam tolerance $\delta = 4\text{ px}$:

1. **Primary Screen Corner Set:**
   $$\mathcal{C}_p = \{ (0, 0), (W_p - 1, 0), (0, H_p - 1), (W_p - 1, H_p - 1) \}$$
2. **Virtual Desktop Corner Set:**
   $$\mathcal{C}_v = \{ (X_v, Y_v), (X_v + W_v - 1, Y_v), (X_v, Y_v + H_v - 1), (X_v + W_v - 1, Y_v + H_v - 1) \}$$
3. **Slam Condition:**
   $$\text{IsCornerSlam}(x, y) \iff \exists (x_c, y_c) \in (\mathcal{C}_p \cup \mathcal{C}_v) \text{ s.t. } |x - x_c| \le \delta \land |y - y_c| \le \delta$$

---

## 4. Class Architecture & Interface Contracts

```
+-------------------------------------------------------------+
|                 parasite_ai.hands.keyboard                  |
+-------------------------------------------------------------+
|  IInputBackend (Protocol)                                   |
|    ├── Win32InputBackend (Real SendInput via user32)         |
|    └── MockInputBackend  (Event recording & virtual time)    |
|                                                             |
|  KeyboardDriver                                             |
|    ├── type_text(text, submit, token) -> bool               |
|    ├── click_and_type(x, y, text, submit, token) -> bool    |
|    ├── hotkey(*keys, token) -> bool                         |
|    ├── emergency_release_keys() -> None                     |
|    └── decompose_utf16(char) -> list[int]                   |
+-------------------------------------------------------------+
                               |
                               | uses backend & coordinates
                               v
+-------------------------------------------------------------+
|                  parasite_ai.safety.panic                   |
+-------------------------------------------------------------+
|  PanicManager                                               |
|    ├── check_key_event(vk, is_up, is_injected, state)       |
|    ├── check_mouse_position(x, y, is_injected)              |
|    ├── trigger_panic(reason) -> None                        |
|    ├── is_panic() -> bool                                   |
|    ├── reset_panic() -> None                                |
|    ├── emergency_hardware_release() -> None                 |
|    └── register_panic_callback(fn)                          |
+-------------------------------------------------------------+
```

### 4.1 `IInputBackend` and Backend Implementations

```python
class CapturedInputEvent:
    def __init__(self, event_type: int, vk: int = 0, scan: int = 0, flags: int = 0, dx: int = 0, dy: int = 0):
        self.type = event_type
        self.vk = vk
        self.scan = scan
        self.flags = flags
        self.dx = dx
        self.dy = dy
        self.timestamp = time.perf_counter()

    def __repr__(self):
        return f"<Event type={self.type} vk=0x{self.vk:02X} scan=0x{self.scan:04X} flags=0x{self.flags:04X}>"

class IInputBackend(Protocol):
    def send_inputs(self, inputs: List[INPUT]) -> int:
        """Dispatches an array of INPUT structures."""
        ...

    def sleep_interruptible(self, duration_s: float, cancellation_token: Optional[threading.Event]) -> bool:
        """Sleeps for duration_s or until cancellation_token is set. Returns True if interrupted."""
        ...

    def get_cursor_pos(self) -> Tuple[int, int]:
        """Returns current cursor (x, y)."""
        ...

    def get_screen_metrics(self) -> Tuple[int, int, int, int, int, int]:
        """Returns (cx, cy, vx, vy, vcx, vcy)."""
        ...
```

#### `Win32InputBackend`
```python
class Win32InputBackend:
    def __init__(self):
        self._user32 = ctypes.windll.user32
        self._user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self._user32.SendInput.restype = wintypes.UINT

    def send_inputs(self, inputs: List[INPUT]) -> int:
        n = len(inputs)
        if n == 0:
            return 0
        arr = (INPUT * n)(*inputs)
        return self._user32.SendInput(n, arr, ctypes.sizeof(INPUT))

    def sleep_interruptible(self, duration_s: float, cancellation_token: Optional[threading.Event]) -> bool:
        if cancellation_token is None:
            time.sleep(duration_s)
            return False
        return cancellation_token.wait(timeout=duration_s)

    def get_cursor_pos(self) -> Tuple[int, int]:
        pt = wintypes.POINT()
        self._user32.GetCursorPos(ctypes.byref(pt))
        return (pt.x, pt.y)

    def get_screen_metrics(self) -> Tuple[int, int, int, int, int, int]:
        cx = self._user32.GetSystemMetrics(SM_CXSCREEN)
        cy = self._user32.GetSystemMetrics(SM_CYSCREEN)
        vx = self._user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = self._user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vcx = self._user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        vcy = self._user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        return (cx, cy, vx, vy, vcx, vcy)
```

#### `MockInputBackend`
```python
class MockInputBackend:
    def __init__(self, virtual_time: bool = True, screen_metrics: Tuple[int, int, int, int, int, int] = (1920, 1080, 0, 0, 1920, 1080)):
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
                    flags=inp.u.ki.dwFlags
                )
                self.events.append(ev)
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
                    dy=inp.u.mi.dy
                )
                self.events.append(ev)
        return len(inputs)

    def sleep_interruptible(self, duration_s: float, cancellation_token: Optional[threading.Event]) -> bool:
        self._bound_token = cancellation_token
        if cancellation_token and cancellation_token.is_set():
            return True
        if not self.virtual_time:
            if cancellation_token:
                return cancellation_token.wait(timeout=duration_s)
            time.sleep(duration_s)
            return False
        return False

    def get_cursor_pos(self) -> Tuple[int, int]:
        return self.cursor_pos

    def set_cursor_pos(self, x: int, y: int) -> None:
        self.cursor_pos = (x, y)

    def get_screen_metrics(self) -> Tuple[int, int, int, int, int, int]:
        return self.screen_metrics

    # Inspection Helpers for Testing
    def get_typed_unicode_scans(self) -> List[int]:
        """Returns sequence of wScan values for KEYEVENTF_UNICODE down events."""
        return [
            e.scan for e in self.events
            if e.type == INPUT_KEYBOARD and (e.flags & KEYEVENTF_UNICODE) and not (e.flags & KEYEVENTF_KEYUP)
        ]

    def get_vk_down_events(self) -> List[int]:
        """Returns sequence of wVk values for virtual-key down events."""
        return [
            e.vk for e in self.events
            if e.type == INPUT_KEYBOARD and not (e.flags & KEYEVENTF_UNICODE) and not (e.flags & KEYEVENTF_KEYUP)
        ]

    def clear(self) -> None:
        self.events.clear()
```

---

### 4.2 `KeyboardDriver` Class Specification

File: `parasite_ai/hands/keyboard.py`

```python
class KeyboardDriver:
    """
    Physical Unicode Keyboard Driver for ParasiteAI.
    Injects keystrokes via Win32 SendInput using KEYEVENTF_UNICODE (0x0004),
    splits astral plane emojis into UTF-16 surrogate pairs, enforces Shift+Enter
    multiline safety, applies human cadence jitter, and guarantees <2ms abort
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
                    # Intermediate newline -> Shift + Enter to avoid premature form submit
                    if not self._send_shift_enter(cancellation_token):
                        return False
            else:
                # Direct Unicode character injection (including surrogate pairs)
                if not self._send_unicode_char(char, cancellation_token):
                    return False

            # Cadence jitter pause between keystrokes
            if not is_final_char:
                pause_s = self._calculate_inter_key_delay(char, jitter_bounds)
                if self.backend.sleep_interruptible(pause_s, cancellation_token):
                    self.emergency_release_keys()
                    return False

        # If submit requested but text didn't end with newline, send final Enter
        if submit and not normalized.endswith("\n"):
            pause_s = random.uniform(0.08, 0.15)
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
        Atomic sequence:
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
            "ctrl": VK_CONTROL, "control": VK_CONTROL,
            "alt": VK_MENU, "menu": VK_MENU,
            "shift": VK_SHIFT,
            "enter": VK_RETURN, "return": VK_RETURN,
            "esc": VK_ESCAPE, "escape": VK_ESCAPE,
            "tab": VK_TAB, "backspace": VK_BACK,
            "space": VK_SPACE,
            "p": VK_P,
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
            self.backend.sleep_interruptible(0.015, cancellation_token)

        # Brief hold
        self.backend.sleep_interruptible(0.030, cancellation_token)

        # Key Ups in reverse order
        for vk in reversed(vks):
            self._send_vk_event(vk, down=False)
            self._held_keys.discard(vk)
            self.backend.sleep_interruptible(0.010, cancellation_token)

        return True

    def emergency_release_keys(self) -> None:
        """
        Releases all currently tracked held keys and vital modifier keys.
        """
        keys_to_release = set(self._held_keys) | {
            VK_SHIFT, VK_LSHIFT, VK_RSHIFT,
            VK_CONTROL, VK_LCONTROL, VK_RCONTROL,
            VK_MENU, VK_LMENU, VK_RMENU
        }
        for vk in keys_to_release:
            self._send_vk_event(vk, down=False)
        self._held_keys.clear()

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------
    def _send_unicode_char(self, char: str, cancellation_token: Optional[threading.Event]) -> bool:
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

            # Interruptible dwell time
            if self.backend.sleep_interruptible(dwell_s, cancellation_token):
                # Send key up immediately before aborting to avoid hanging character
                inp_up = INPUT(type=INPUT_KEYBOARD)
                inp_up.u.ki.wVk = 0
                inp_up.u.ki.wScan = w
                inp_up.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
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
            # 4% chance of cognitive micro-hesitation
            if random.random() < self.config.micro_pause_probability:
                return random.uniform(0.200, 0.500)

        # Log-Normal Cadence Jitter
        # mu=3.8 -> exp(3.8) ~= 44.7ms
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
```

---

### 4.3 `PanicManager` Specification

File: `parasite_ai/safety/panic.py`

```python
class PanicTriggerSource:
    ESC_KEY = "esc_key"
    CTRL_ALT_P = "ctrl_alt_p"
    CTRL_ALT_BACKSPACE = "ctrl_alt_backspace"
    CORNER_SLAM = "corner_slam"
    MANUAL = "manual"

class PanicManager:
    """
    Multi-Layered Global Panic Abort Subsystem.
    Monitors global hotkeys (Esc, Ctrl+Alt+P, Ctrl+Alt+Backspace), screen corner slam,
    signals panic events, and neutralizes hardware states (releases stuck keys and buttons).
    """

    def __init__(
        self,
        config: Optional[SafetyConfig] = None,
        backend: Optional[IInputBackend] = None,
        on_panic_callback: Optional[Callable[[str], None]] = None,
    ):
        self.config = config or SafetyConfig()
        self.backend = backend or Win32InputBackend()
        self.on_panic_callback = on_panic_callback

        self._panic_event = threading.Event()
        self._panic_reason: Optional[str] = None
        self._callbacks: List[Callable[[str], None]] = []
        if on_panic_callback:
            self._callbacks.append(on_panic_callback)

        # Internal modifier tracking for both live hooks and test simulation
        self._is_ctrl_down = False
        self._is_alt_down = False
        self._is_shift_down = False

    def is_panic(self) -> bool:
        return self._panic_event.is_set()

    def get_panic_event(self) -> threading.Event:
        return self._panic_event

    def get_panic_reason(self) -> Optional[str]:
        return self._panic_reason

    def register_callback(self, callback: Callable[[str], None]) -> None:
        self._callbacks.append(callback)

    def trigger_panic(self, source: str) -> None:
        """
        Activates emergency panic: sets event, neutralizes hardware state,
        and fires registered callbacks immediately.
        """
        self._panic_reason = source
        self._panic_event.set()
        self.emergency_hardware_release()

        for cb in self._callbacks:
            try:
                cb(source)
            except Exception:
                pass

    def reset_panic(self) -> None:
        """Resets panic state (e.g. user clicked Resume in Dock)."""
        self._panic_event.clear()
        self._panic_reason = None

    def emergency_hardware_release(self) -> None:
        """
        Clears all held mouse buttons and modifier keys (Shift, Ctrl, Alt).
        Guarantees zero stuck-key or stuck-drag state.
        """
        # 1. Mouse Button Release
        mouse_inp = INPUT(type=INPUT_MOUSE)
        mouse_inp.u.mi.dwFlags = MOUSEEVENTF_LEFTUP | MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_MIDDLEUP
        self.backend.send_inputs([mouse_inp])

        # 2. Modifier Key Release
        vks = [
            VK_SHIFT, VK_LSHIFT, VK_RSHIFT,
            VK_CONTROL, VK_LCONTROL, VK_RCONTROL,
            VK_MENU, VK_LMENU, VK_RMENU
        ]
        key_inputs = []
        for vk in vks:
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.u.ki.wVk = vk
            inp.u.ki.wScan = 0
            inp.u.ki.dwFlags = KEYEVENTF_KEYUP
            key_inputs.append(inp)
        self.backend.send_inputs(key_inputs)

        # Reset tracked states
        self._is_ctrl_down = False
        self._is_alt_down = False
        self._is_shift_down = False

    def check_key_event(
        self,
        vk_code: int,
        flags: int,
        active_state: str = "DRIVING",
    ) -> bool:
        """
        Inspects low-level keyboard hook parameters.
        Returns True if a panic trigger was activated, False otherwise.
        """
        is_injected = bool(flags & LLKHF_INJECTED)
        if is_injected:
            # Synthetic inputs never trigger panic
            return False

        is_key_up = bool(flags & LLKHF_UP)

        # Update modifier states
        if vk_code in (VK_CONTROL, VK_LCONTROL, VK_RCONTROL):
            self._is_ctrl_down = not is_key_up
        elif vk_code in (VK_MENU, VK_LMENU, VK_RMENU):
            self._is_alt_down = not is_key_up
        elif vk_code in (VK_SHIFT, VK_LSHIFT, VK_RSHIFT):
            self._is_shift_down = not is_key_up

        if is_key_up:
            return False

        # Also check flags & LLKHF_ALTDOWN as secondary check
        alt_active = self._is_alt_down or bool(flags & LLKHF_ALTDOWN)

        # 1. Esc Key (active when assistant is driving or offloading)
        if vk_code == VK_ESCAPE:
            if active_state in ("DRIVING", "OFFLOADING", "ANY"):
                self.trigger_panic(PanicTriggerSource.ESC_KEY)
                return True

        # 2. Ctrl + Alt + P (System-Wide)
        if vk_code == VK_P and self._is_ctrl_down and alt_active:
            self.trigger_panic(PanicTriggerSource.CTRL_ALT_P)
            return True

        # 3. Ctrl + Alt + Backspace (System-Wide)
        if vk_code == VK_BACK and self._is_ctrl_down and alt_active:
            self.trigger_panic(PanicTriggerSource.CTRL_ALT_BACKSPACE)
            return True

        return False

    def check_mouse_position(
        self,
        x: int,
        y: int,
        flags: int = 0,
    ) -> bool:
        """
        Inspects low-level mouse coordinates for corner slam.
        Returns True if corner slam panic was triggered.
        """
        is_injected = bool(flags & LLMHF_INJECTED)
        if is_injected or not self.config.corner_panic_enabled:
            return False

        delta = self.config.corner_distance_px
        cx, cy, vx, vy, vcx, vcy = self.backend.get_screen_metrics()

        # Primary monitor corners
        primary_corners = [
            (0, 0),
            (cx - 1, 0),
            (0, cy - 1),
            (cx - 1, cy - 1),
        ]

        # Virtual desktop corners
        virtual_corners = [
            (vx, vy),
            (vx + vcx - 1, vy),
            (vx, vy + vcy - 1),
            (vx + vcx - 1, vy + vcy - 1),
        ]

        all_corners = primary_corners + virtual_corners
        for cx_k, cy_k in all_corners:
            if abs(x - cx_k) <= delta and abs(y - cy_k) <= delta:
                self.trigger_panic(PanicTriggerSource.CORNER_SLAM)
                return True

        return False
```

---

## 5. Test Suite Specifications for Worker

### 5.1 `tests/test_keyboard_driver.py`

| Test Function | Target Feature | Acceptance Criteria |
|---|---|---|
| `test_ctypes_input_size_and_alignment` | 64-bit ABI | `sizeof(INPUT) == 40`, `INPUT.u.offset == 8`, `sizeof(KEYBDINPUT) == 24`, `sizeof(MOUSEINPUT) == 32`. |
| `test_decompose_utf16_bmp` | Astral plane | ASCII, accented, CJK (`'A'`, `'é'`, `'中'`) return single code unit list `[ord(c)]`. |
| `test_decompose_utf16_astral_emojis` | Astral plane | 🤖 (`U+1F916` $\to [0xD83E, 0xDD16]$), 🌍 (`U+1F30D` $\to [0xD83C, 0xDF0D]$), 🚀 (`U+1F680` $\to [0xD83D, 0xDE80]$). Matches `struct.unpack('<2H', char.encode('utf-16-le'))`. |
| `test_type_text_bmp_keys` | Unicode typing | Types `"Hello"`: asserts `wVk == 0`, `wScan == ord(c)`, `dwFlags == KEYEVENTF_UNICODE` (down) and `KEYEVENTF_UNICODE \| KEYEVENTF_KEYUP` (up). |
| `test_type_text_astral_emojis` | Unicode typing | Types `"AI 🤖!"`: verifies surrogate pairs emitted sequentially with proper down/up pairs. |
| `test_multiline_shift_enter_intermediate` | Multiline safety | Types `"line1\nline2"` with `submit=False`: verifies `\n` emits `VK_SHIFT` down $\to$ `VK_RETURN` down/up $\to$ `VK_SHIFT` up. Plain `VK_RETURN` is NOT emitted. |
| `test_multiline_submit_true_final_enter` | Multiline safety | Types `"query\n"` with `submit=True`: verifies final `\n` emits plain `VK_RETURN` (no `VK_SHIFT`). |
| `test_submit_without_trailing_newline` | Multiline safety | Types `"search query"` with `submit=True`: types text followed by plain `VK_RETURN`. |
| `test_crlf_normalization` | String parsing | Types `"A\r\nB\rC"`: converts to clean single newline transitions. |
| `test_per_keystroke_interrupt_abort` | Safety interrupt | Binds cancellation token that triggers after character 3 of a 10-character string: `type_text` returns `False`, stops typing immediately, releases keys. |
| `test_per_keystroke_abort_releases_shift` | Safety interrupt | Cancels token while Shift is held during `Shift+Enter`: verifies `emergency_release_keys()` releases Shift immediately. |
| `test_atomic_click_and_type_success` | Atomic focus | Calls `click_and_type(500, 300, "hello")`: verifies mouse click events dispatched, focus delay observed, text typed. |
| `test_atomic_click_and_type_cancelled_in_focus` | Atomic focus | Cancels token during the 75ms focus wait: aborts before typing any character, returns `False`. |
| `test_hotkey_execution` | Hotkey helper | Calls `hotkey('ctrl', 'c')`: verifies `VK_CONTROL` down $\to$ `'C'` down $\to$ `'C'` up $\to$ `VK_CONTROL` up. |

### 5.2 `tests/test_panic.py`

| Test Function | Target Feature | Acceptance Criteria |
|---|---|---|
| `test_panic_esc_during_driving` | Hotkey panic | `check_key_event(VK_ESCAPE, flags=0, active_state="DRIVING")` triggers panic, sets event, reason is `esc_key`. |
| `test_panic_esc_ignored_when_idle` | State selectivity | `check_key_event(VK_ESCAPE, flags=0, active_state="IDLE")` does NOT trigger panic. |
| `test_panic_ctrl_alt_p_system_wide` | Hotkey panic | Simulates Ctrl down $\to$ Alt down $\to$ `VK_P`: triggers panic, reason is `ctrl_alt_p`. |
| `test_panic_ctrl_alt_backspace_system_wide` | Hotkey panic | Simulates Ctrl down $\to$ Alt down $\to$ `VK_BACK`: triggers panic, reason is `ctrl_alt_backspace`. |
| `test_panic_ignores_synthetic_injected_keys` | Filter safety | Simulates `VK_ESCAPE` or `VK_P` with `flags=LLKHF_INJECTED (0x10)`: does NOT trigger panic. |
| `test_panic_corner_slam_all_four_corners` | Corner slam | Tests $(2, 2)$, $(1918, 2)$, $(2, 1078)$, $(1918, 1078)$: all trigger corner slam panic. |
| `test_panic_corner_slam_safe_regions` | Corner slam | Tests $(10, 10)$, $(960, 540)$, $(1900, 1000)$: does NOT trigger panic. |
| `test_panic_corner_slam_ignores_injected_mouse` | Filter safety | Tests $(2, 2)$ with `flags=LLMHF_INJECTED (0x01)`: does NOT trigger panic. |
| `test_emergency_hardware_release_called_on_panic` | State reset | Verifies that on panic, `MOUSEEVENTF_LEFTUP | MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_MIDDLEUP` and `KEYEVENTF_KEYUP` for Shift, Ctrl, Alt are sent to backend. |
| `test_panic_callbacks_and_reset` | Lifecycle | Verifies registered callbacks are invoked with source string; calling `reset_panic()` clears event. |

---

## 6. Implementation Checklist for Worker

1. **Create directories:**
   - `parasite_ai/hands/`
   - `parasite_ai/safety/`
2. **Implement `parasite_ai/hands/keyboard.py`:**
   - Win32 structs (`INPUT`, `KEYBDINPUT`, `MOUSEINPUT`, `HARDWAREINPUT`, `INPUT_UNION`) with 40-byte assertion.
   - `IInputBackend`, `Win32InputBackend`, `MockInputBackend`.
   - `KeyboardDriver` with UTF-16 surrogate pairs, `Shift+Enter`, cadence jitter, interrupt checking, atomic `click_and_type`, and hotkey execution.
3. **Implement `parasite_ai/safety/panic.py`:**
   - `PanicManager` and `PanicTriggerSource`.
   - Esc, Ctrl+Alt+P, Ctrl+Alt+Backspace evaluation.
   - Screen corner slam mathematical detection.
   - Emergency hardware state release (`MOUSEEVENTF_*UP`, `VK_*` keyup).
4. **Implement test suites:**
   - `tests/test_keyboard_driver.py` (all 14 test cases).
   - `tests/test_panic.py` (all 10 test cases).
5. **Execute verification:**
   - Run `uv run pytest tests/test_keyboard_driver.py tests/test_panic.py -v`.
   - Ensure 100% test pass rate with zero warnings.
