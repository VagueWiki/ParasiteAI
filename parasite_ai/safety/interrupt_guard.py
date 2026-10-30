"""
ParasiteAI - Win32 Low-Level Hardware Hook Interrupt & Safety Guard.
Enforces sub-2ms physical hardware preemption, panic hotkeys, and sliding cooldown.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import threading
import time
from typing import Callable, Optional, Tuple

from parasite_ai.safety.panic import PanicManager, PanicTriggerSource


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class PhysicalInterruptException(RuntimeError):
    """Raised when physical mouse or keyboard input preempts active automation."""
    pass


class PanicInterruptException(PhysicalInterruptException):
    """Raised when an emergency panic hotkey (Esc, Ctrl+Alt+P, Ctrl+Alt+Backspace) or corner slam fires."""
    pass


# ---------------------------------------------------------------------------
# Win32 Constants
# ---------------------------------------------------------------------------
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_QUIT = 0x0012

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_MOUSEHWHEEL = 0x020E

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

LLMHF_INJECTED = 0x00000001
LLMHF_LOWER_IL_INJECTED = 0x00000002

LLKHF_EXTENDED = 0x00000001
LLKHF_INJECTED = 0x00000010
LLKHF_ALTDOWN = 0x00000020
LLKHF_UP = 0x00000080

VK_BACK = 0x08
VK_ESCAPE = 0x1B
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_P = 0x50

MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEUP = 0x0040
KEYEVENTF_KEYUP = 0x0002


# ---------------------------------------------------------------------------
# Ctypes Struct Definitions (Verified 64-bit Memory Layout)
# ---------------------------------------------------------------------------
class POINT(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    """
    64-bit Memory Layout: Total Size = 32 bytes
    Offset 0:  pt (POINT, 8 bytes: LONG x at 0, LONG y at 4)
    Offset 8:  mouseData (DWORD, 4 bytes)
    Offset 12: flags (DWORD, 4 bytes: contains LLMHF_INJECTED bit 0)
    Offset 16: time (DWORD, 4 bytes)
    Offset 20: [4 bytes compiler padding]
    Offset 24: dwExtraInfo (ULONG_PTR / c_size_t, 8 bytes)
    """
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    """
    64-bit Memory Layout: Total Size = 24 bytes
    Offset 0:  vkCode (DWORD, 4 bytes)
    Offset 4:  scanCode (DWORD, 4 bytes)
    Offset 8:  flags (DWORD, 4 bytes: contains LLKHF_INJECTED bit 4 = 0x10)
    Offset 12: time (DWORD, 4 bytes)
    Offset 16: dwExtraInfo (ULONG_PTR / c_size_t, 8 bytes)
    """
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(
    wintypes.LPARAM,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


assert ctypes.sizeof(MSLLHOOKSTRUCT) == 32, f"MSLLHOOKSTRUCT must be 32 bytes, got {ctypes.sizeof(MSLLHOOKSTRUCT)}"
assert ctypes.sizeof(KBDLLHOOKSTRUCT) == 24, f"KBDLLHOOKSTRUCT must be 24 bytes, got {ctypes.sizeof(KBDLLHOOKSTRUCT)}"


# ---------------------------------------------------------------------------
# InterruptGuard
# ---------------------------------------------------------------------------
class InterruptGuard:
    """
    Win32 low-level hook interrupt monitor.
    Inspects LLMHF_INJECTED and LLKHF_INJECTED flags on a dedicated thread,
    signaling cross-thread cancellation in < 2ms upon physical hardware touch.
    """

    def __init__(
        self,
        cooldown_seconds: float = 10.0,
        corner_panic_enabled: bool = True,
        corner_distance_px: int = 4,
        on_interrupt_callback: Optional[Callable[[str], None]] = None,
        on_panic_callback: Optional[Callable[[str], None]] = None,
        on_rearm_callback: Optional[Callable[[], None]] = None,
        panic_manager: Optional[PanicManager] = None,
    ):
        self._cooldown_seconds = float(cooldown_seconds)
        self._corner_panic_enabled = corner_panic_enabled
        self._corner_distance_px = int(corner_distance_px)
        self._on_interrupt_callback = on_interrupt_callback
        self._on_panic_callback = on_panic_callback
        self._on_rearm_callback = on_rearm_callback

        # Synchronization & State
        self._lock = threading.Lock()
        self._cancellation_token = threading.Event()
        self._interrupted = False
        self._last_interrupt_time = 0.0
        self._rearm_timer: Optional[threading.Timer] = None

        # Panic Subsystem Integration
        self.panic_manager = panic_manager or PanicManager(
            on_panic_callback=self._handle_panic_event
        )

        # Hook Thread Infrastructure
        self._hook_thread: Optional[threading.Thread] = None
        self._hook_thread_id: int = 0
        self._thread_ready_event = threading.Event()
        self._is_running = False

        # Native Hook Handles & Retained Callbacks (prevent GC)
        self._mouse_hook = None
        self._keyboard_hook = None
        self._mouse_proc_cb = None
        self._keyboard_proc_cb = None

        # Win32 Function Bindings
        self._init_win32_bindings()

    def _init_win32_bindings(self) -> None:
        try:
            self._user32 = ctypes.windll.user32
            self._kernel32 = ctypes.windll.kernel32
            self._winmm = ctypes.windll.winmm

            self._user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
            self._user32.SetWindowsHookExW.restype = wintypes.HHOOK

            self._user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
            self._user32.UnhookWindowsHookEx.restype = wintypes.BOOL

            self._user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
            self._user32.CallNextHookEx.restype = wintypes.LPARAM

            self._user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            self._user32.GetMessageW.restype = wintypes.BOOL

            self._user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
            self._user32.TranslateMessage.restype = wintypes.BOOL

            self._user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
            self._user32.DispatchMessageW.restype = wintypes.LPARAM

            self._user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
            self._user32.PeekMessageW.restype = wintypes.BOOL

            self._user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            self._user32.PostThreadMessageW.restype = wintypes.BOOL

            self._kernel32.GetCurrentThreadId.argtypes = []
            self._kernel32.GetCurrentThreadId.restype = wintypes.DWORD

            self._kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            self._kernel32.GetModuleHandleW.restype = wintypes.HMODULE

            self._winmm.timeBeginPeriod.argtypes = [wintypes.UINT]
            self._winmm.timeBeginPeriod.restype = wintypes.UINT

            self._winmm.timeEndPeriod.argtypes = [wintypes.UINT]
            self._winmm.timeEndPeriod.restype = wintypes.UINT
        except Exception as e:
            logger.warning(f"InterruptGuard Win32 bindings initialization warning: {e}")

    def _handle_panic_event(self, reason: str) -> None:
        """Triggered when PanicManager detects a panic condition."""
        self._cancellation_token.set()
        with self._lock:
            self._interrupted = True
            self._last_interrupt_time = time.monotonic()
        if self._on_panic_callback:
            try:
                self._on_panic_callback(reason)
            except Exception:
                pass

    def start(self) -> None:
        """Starts the dedicated hook thread and enables 1ms timer precision."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._interrupted = False
            self._cancellation_token.clear()
            self._thread_ready_event.clear()

        try:
            self._winmm.timeBeginPeriod(1)
        except Exception:
            pass

        import os
        if self.panic_manager and not os.environ.get("PYTEST_CURRENT_TEST"):
            self.panic_manager.allow_process_exit = True

        self._hook_thread = threading.Thread(
            target=self._hook_thread_entry,
            name="InterruptGuardHookThread",
            daemon=True,
        )
        self._hook_thread.start()

        # Wait up to 2.0s for the hook thread to instantiate its message queue and hooks
        self._thread_ready_event.wait(timeout=2.0)

    def stop(self) -> None:
        """Unhooks procedures, terminates hook thread, and restores timer period."""
        with self._lock:
            if not self._is_running:
                return
            self._is_running = False

            if self._rearm_timer is not None:
                self._rearm_timer.cancel()
                self._rearm_timer = None

        if self._hook_thread_id != 0:
            try:
                self._user32.PostThreadMessageW(self._hook_thread_id, WM_QUIT, 0, 0)
            except Exception as e:
                logger.warning(f"Error posting WM_QUIT to hook thread: {e}")

        if self._hook_thread is not None and self._hook_thread.is_alive():
            self._hook_thread.join(timeout=2.0)
            self._hook_thread = None

        try:
            self._winmm.timeEndPeriod(1)
        except Exception:
            pass

    def is_interrupted(self) -> bool:
        """Returns True if physical input or panic interrupted actions and cooldown has not expired."""
        with self._lock:
            if self._panic_manager_is_panic():
                return True
            if not self._interrupted:
                return False
            # Check if sliding cooldown elapsed
            if time.monotonic() - self._last_interrupt_time >= self._cooldown_seconds:
                self._interrupted = False
                self._cancellation_token.clear()
                return False
            return True

    def _panic_manager_is_panic(self) -> bool:
        return self.panic_manager.is_panic() if self.panic_manager else False

    def is_panic(self) -> bool:
        """Returns True if emergency panic has been triggered."""
        return self._panic_manager_is_panic()

    def get_cancellation_token(self) -> threading.Event:
        """Returns the atomic threading.Event signaled immediately on physical touch."""
        return self._cancellation_token

    def reset_interrupt(self) -> None:
        """Clears interrupt state, cancellation token, and resets panic state."""
        with self._lock:
            self._interrupted = False
            self._cancellation_token.clear()
            self._last_interrupt_time = 0.0
            if self._rearm_timer is not None:
                self._rearm_timer.cancel()
                self._rearm_timer = None

        if self.panic_manager:
            self.panic_manager.reset_panic()

    def wait_interruptible(self, timeout: float) -> bool:
        """
        Sleeps up to `timeout` seconds or until cancellation_token is set.
        Returns True if the full timeout elapsed without interruption.
        Returns False immediately (< 2ms) if interrupted by physical touch or panic.
        """
        interrupted = self._cancellation_token.wait(timeout=timeout)
        return not interrupted

    # -----------------------------------------------------------------------
    # Low-Level Hook Thread Logic
    # -----------------------------------------------------------------------
    def _hook_thread_entry(self) -> None:
        self._hook_thread_id = self._kernel32.GetCurrentThreadId()

        # Force message queue instantiation
        msg = wintypes.MSG()
        self._user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 0)

        # Retain strong callback references on self to prevent GC crashes (0xC0000005)
        self._mouse_proc_cb = HOOKPROC(self._low_level_mouse_proc)
        self._keyboard_proc_cb = HOOKPROC(self._low_level_keyboard_proc)

        h_mod = self._kernel32.GetModuleHandleW(None)

        self._mouse_hook = self._user32.SetWindowsHookExW(
            WH_MOUSE_LL,
            self._mouse_proc_cb,
            h_mod,
            0,
        )
        self._keyboard_hook = self._user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._keyboard_proc_cb,
            h_mod,
            0,
        )

        if not self._mouse_hook or not self._keyboard_hook:
            logger.warning(
                f"SetWindowsHookExW returned null (mouse={bool(self._mouse_hook)}, "
                f"kbd={bool(self._keyboard_hook)}). Running in simulation fallback mode."
            )

        # Register OS-level kernel hotkeys for instant kill (Ctrl+Alt+K = 9001, Ctrl+Alt+Q = 9002)
        try:
            self._user32.RegisterHotKey(None, 9001, 0x0001 | 0x0002 | 0x4000, 0x4B)  # MOD_ALT | MOD_CONTROL | MOD_NOREPEAT, VK_K
            self._user32.RegisterHotKey(None, 9002, 0x0001 | 0x0002 | 0x4000, 0x51)  # MOD_ALT | MOD_CONTROL | MOD_NOREPEAT, VK_Q
        except Exception:
            pass

        self._thread_ready_event.set()

        # Message pump
        while self._user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            if msg.message == 0x0312 and msg.wParam in (9001, 9002):  # WM_HOTKEY
                if self._mouse_hook:
                    self._user32.UnhookWindowsHookEx(self._mouse_hook)
                    self._mouse_hook = None
                if self._keyboard_hook:
                    self._user32.UnhookWindowsHookEx(self._keyboard_hook)
                    self._keyboard_hook = None
                if self.panic_manager:
                    self.panic_manager.trigger_panic(PanicTriggerSource.CTRL_ALT_K_KILL)
                break
            self._user32.TranslateMessage(ctypes.byref(msg))
            self._user32.DispatchMessageW(ctypes.byref(msg))

        # Unhook upon WM_QUIT exit
        try:
            self._user32.UnregisterHotKey(None, 9001)
            self._user32.UnregisterHotKey(None, 9002)
        except Exception:
            pass
        if self._mouse_hook:
            self._user32.UnhookWindowsHookEx(self._mouse_hook)
            self._mouse_hook = None
        if self._keyboard_hook:
            self._user32.UnhookWindowsHookEx(self._keyboard_hook)
            self._keyboard_hook = None

    def _low_level_mouse_proc(self, n_code: int, w_param: int, l_param: int) -> int:
        if n_code >= 0 and l_param:
            try:
                struct = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                is_injected = bool(struct.flags & LLMHF_INJECTED)

                if not is_injected:
                    # Physical mouse event detected!
                    # First check corner slam panic
                    if self._corner_panic_enabled and self.panic_manager:
                        if self.panic_manager.check_mouse_position(struct.pt.x, struct.pt.y, flags=struct.flags):
                            return self._user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)

                    # Signal physical interrupt
                    self._signal_physical_touch(f"mouse_msg_0x{w_param:04X}_at_({struct.pt.x},{struct.pt.y})")
            except Exception as e:
                logger.error(f"Error in _low_level_mouse_proc: {e}")

        return self._user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)

    def _low_level_keyboard_proc(self, n_code: int, w_param: int, l_param: int) -> int:
        if n_code >= 0 and l_param:
            try:
                struct = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                is_injected = bool(struct.flags & LLKHF_INJECTED)

                if not is_injected:
                    # Physical keyboard event detected!
                    # First check panic hotkeys
                    if self.panic_manager:
                        if self.panic_manager.check_key_event(struct.vkCode, flags=struct.flags):
                            return self._user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)

                    # Signal physical interrupt
                    self._signal_physical_touch(f"keyboard_vk_0x{struct.vkCode:02X}")
            except Exception as e:
                logger.error(f"Error in _low_level_keyboard_proc: {e}")

        return self._user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)

    def _signal_physical_touch(self, source_desc: str) -> None:
        """Sets cancellation token, updates cooldown timestamp, and starts sliding rearm timer."""
        self._cancellation_token.set()
        now = time.monotonic()
        with self._lock:
            self._interrupted = True
            self._last_interrupt_time = now

            # Sliding cooldown: _on_rearm_timer_fired reschedules itself for the remaining time,
            # so only one timer needs to be pending (avoids per-event thread creation latency).
            if self._rearm_timer is None:
                self._rearm_timer = threading.Timer(self._cooldown_seconds, self._on_rearm_timer_fired)
                self._rearm_timer.daemon = True
                self._rearm_timer.start()

        if self._on_interrupt_callback:
            try:
                self._on_interrupt_callback(source_desc)
            except Exception:
                pass

    def _on_rearm_timer_fired(self) -> None:
        """Fires when sliding cooldown expires with no subsequent physical touches."""
        rearmed = False
        with self._lock:
            elapsed = time.monotonic() - self._last_interrupt_time
            if elapsed >= self._cooldown_seconds - 0.05:
                self._interrupted = False
                self._cancellation_token.clear()
                self._rearm_timer = None
                rearmed = True
            else:
                remaining = self._cooldown_seconds - elapsed
                self._rearm_timer = threading.Timer(remaining, self._on_rearm_timer_fired)
                self._rearm_timer.daemon = True
                self._rearm_timer.start()

        if rearmed and self._on_rearm_callback:
            try:
                self._on_rearm_callback()
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # Deterministic Hook Simulation Harness (for Automated Tests)
    # -----------------------------------------------------------------------
    def simulate_event(
        self,
        event_type: str,
        flags: int = 0,
        vk_code: int = 0,
        pt: Tuple[int, int] = (0, 0),
        w_param: Optional[int] = None,
    ) -> None:
        """
        Software hook event simulation harness for automated testing.
        Dispatches synthetic or simulated physical events directly to the hook procedures.
        """
        if event_type == "mouse":
            msg = w_param if w_param is not None else WM_MOUSEMOVE
            struct = MSLLHOOKSTRUCT(
                pt=POINT(x=pt[0], y=pt[1]),
                mouseData=0,
                flags=flags,
                time=int(time.time() * 1000) & 0xFFFFFFFF,
                dwExtraInfo=0,
            )
            self._low_level_mouse_proc(0, msg, ctypes.addressof(struct))
        elif event_type == "keyboard":
            msg = w_param if w_param is not None else (WM_KEYUP if (flags & LLKHF_UP) else WM_KEYDOWN)
            struct = KBDLLHOOKSTRUCT(
                vkCode=vk_code,
                scanCode=0,
                flags=flags,
                time=int(time.time() * 1000) & 0xFFFFFFFF,
                dwExtraInfo=0,
            )
            self._low_level_keyboard_proc(0, msg, ctypes.addressof(struct))
        else:
            raise ValueError(f"Unknown event_type: {event_type}")
