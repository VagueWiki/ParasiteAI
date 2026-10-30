"""
ParasiteAI - Global Panic Abort Subsystem.
Monitors emergency panic triggers (Esc, Ctrl+Alt+P, Ctrl+Alt+Backspace, Screen Corner Slam),
signals immediate abort, and neutralizes hardware state to release stuck buttons and keys.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import threading
from typing import Any, Callable, List, Optional, Tuple

from parasite_ai.config import SafetyConfig


# Win32 Constants for Panic and Hardware Release
LLMHF_INJECTED = 0x00000001
LLKHF_INJECTED = 0x00000010
LLKHF_ALTDOWN = 0x00000020
LLKHF_UP = 0x00000080

VK_BACK = 0x08
VK_ESCAPE = 0x1B
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt key
VK_K = 0x4B
VK_P = 0x50
VK_Q = 0x51

VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5

MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEUP = 0x0040
KEYEVENTF_KEYUP = 0x0002

SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


class PanicTriggerSource:
    """Identifiers for panic trigger sources."""
    ESC_KEY = "esc_key"
    CTRL_ALT_P = "ctrl_alt_p"
    CTRL_ALT_BACKSPACE = "ctrl_alt_backspace"
    CTRL_ALT_K_KILL = "ctrl_alt_k_kill"
    CORNER_SLAM = "corner_slam"
    MANUAL = "manual"


class PanicManager:
    """
    Multi-layered global panic abort manager.
    Detects physical user panic interactions, halts synthetic execution,
    and neutralizes physical hardware states.
    """

    def __init__(
        self,
        config: Optional[SafetyConfig] = None,
        backend: Optional[Any] = None,
        on_panic_callback: Optional[Callable[[str], None]] = None,
    ):
        self.config = config or SafetyConfig()
        self.backend = backend
        self.on_panic_callback = on_panic_callback

        self._lock = threading.Lock()
        self._panic_event = threading.Event()
        self._panic_reason: Optional[str] = None
        self._callbacks: List[Callable[[str], None]] = []
        if on_panic_callback:
            self._callbacks.append(on_panic_callback)

        # Modifier key tracking
        self._is_ctrl_down = False
        self._is_alt_down = False
        self._is_shift_down = False
        self.allow_process_exit: bool = False

    def is_panic(self) -> bool:
        """Returns True if panic abort is currently triggered."""
        return self._panic_event.is_set()

    def get_panic_event(self) -> threading.Event:
        """Returns the atomic threading.Event set on panic."""
        return self._panic_event

    def get_panic_reason(self) -> Optional[str]:
        """Returns the reason / source for the most recent panic trigger."""
        return self._panic_reason

    def register_callback(self, callback: Callable[[str], None]) -> None:
        """Registers a callback function invoked immediately on panic."""
        with self._lock:
            self._callbacks.append(callback)

    def trigger_panic(self, source: str) -> None:
        """
        Activates emergency panic:
        1. Sets panic event
        2. Neutralizes hardware state (releases stuck buttons/keys)
        3. Invokes all registered panic callbacks
        """
        with self._lock:
            self._panic_reason = source
            self._panic_event.set()
            callbacks = list(self._callbacks)

        self.emergency_hardware_release()

        for cb in callbacks:
            try:
                cb(source)
            except Exception:
                pass

        if source == PanicTriggerSource.CTRL_ALT_K_KILL and self.allow_process_exit:
            self.hard_kill_all_processes()

    def hard_kill_all_processes(self) -> None:
        """
        Instantly neutralizes physical inputs and terminates the entire ParasiteAI process tree.
        """
        import os
        import subprocess
        try:
            self.emergency_hardware_release()
        except Exception:
            pass
        try:
            pid = os.getpid()
            subprocess.Popen(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
        except Exception:
            pass
        os._exit(0)

    def reset_panic(self) -> None:
        """Resets panic state (e.g. user resumed operation)."""
        with self._lock:
            self._panic_event.clear()
            self._panic_reason = None
            self._is_ctrl_down = False
            self._is_alt_down = False
            self._is_shift_down = False

    def emergency_hardware_release(self) -> None:
        """
        Neutralizes hardware state by dispatching key-up and button-up events.
        Prevents dangerous stuck-down modifier or mouse dragging states.
        """
        if self.backend is not None and hasattr(self.backend, "emergency_hardware_release"):
            try:
                self.backend.emergency_hardware_release()
                return
            except Exception:
                pass

        if self.backend is not None and hasattr(self.backend, "send_inputs"):
            # Import INPUT structures lazily if needed
            from parasite_ai.hands.keyboard import INPUT, INPUT_MOUSE, INPUT_KEYBOARD

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
        else:
            # Fall back to user32 direct calls
            try:
                user32 = ctypes.windll.user32
                user32.mouse_event(
                    MOUSEEVENTF_LEFTUP | MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_MIDDLEUP,
                    0, 0, 0, 0
                )
                for vk in [VK_SHIFT, VK_CONTROL, VK_MENU]:
                    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            except Exception:
                pass

        self._is_ctrl_down = False
        self._is_alt_down = False
        self._is_shift_down = False

    def check_key_event(
        self,
        vk_code: int,
        flags: int = 0,
        active_state: str = "DRIVING",
    ) -> bool:
        """
        Inspects keyboard events for panic hotkeys.
        Synthetic (injected) keystrokes are strictly ignored.

        Returns True if a panic trigger fired.
        """
        is_injected = bool(flags & LLKHF_INJECTED)
        if is_injected:
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

        # 4. Ctrl + Alt + K or Ctrl + Alt + Q (Instant Hard Process Kill)
        if vk_code in (VK_K, VK_Q) and self._is_ctrl_down and alt_active:
            self.trigger_panic(PanicTriggerSource.CTRL_ALT_K_KILL)
            return True

        return False

    def check_mouse_position(
        self,
        x: int,
        y: int,
        flags: int = 0,
    ) -> bool:
        """
        Inspects mouse cursor position for screen corner slam.
        Synthetic (injected) cursor movements are strictly ignored.

        Returns True if corner slam panic fired.
        """
        is_injected = bool(flags & LLMHF_INJECTED)
        if is_injected or not self.config.corner_panic_enabled:
            return False

        delta = self.config.corner_distance_px
        cx, cy, vx, vy, vcx, vcy = self._get_screen_metrics()

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

    def _get_screen_metrics(self) -> Tuple[int, int, int, int, int, int]:
        """Returns (cx, cy, vx, vy, vcx, vcy)."""
        if self.backend is not None and hasattr(self.backend, "get_screen_metrics"):
            try:
                return self.backend.get_screen_metrics()
            except Exception:
                pass

        try:
            user32 = ctypes.windll.user32
            cx = user32.GetSystemMetrics(SM_CXSCREEN)
            cy = user32.GetSystemMetrics(SM_CYSCREEN)
            vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            vcx = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            vcy = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            return (cx, cy, vx, vy, vcx, vcy)
        except Exception:
            return (1920, 1080, 0, 0, 1920, 1080)
