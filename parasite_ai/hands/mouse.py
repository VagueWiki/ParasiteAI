"""
ParasiteAI - Win32 Human-Like Mouse Driver.
Executes 120Hz trajectory interpolation with timeBeginPeriod(1), instant interrupt
cancellation (<2ms), pre-click reticle preview hook, and headless simulation mode.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from parasite_ai.config import MouseConfig
from parasite_ai.hands.kinematics import KinematicConfig, KinematicsEngine


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Win32 Constants
# ---------------------------------------------------------------------------
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000
WHEEL_DELTA = 120

SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


# ---------------------------------------------------------------------------
# Ctypes Structs (Verified 40-byte x64 Memory Layout)
# ---------------------------------------------------------------------------
class MOUSEINPUT(ctypes.Structure):
    """32-byte MOUSEINPUT structure."""
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    """
    40-byte INPUT structure on 64-bit Windows.
    Offset 0: type (DWORD, 4 bytes)
    Offset 4: [4 bytes padding]
    Offset 8: _u (Union, 32 bytes)
    """
    _anonymous_ = ("_u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_u", _INPUT_UNION),
    ]

    @property
    def u(self) -> _INPUT_UNION:
        return self._u


assert ctypes.sizeof(MOUSEINPUT) == 32, f"MOUSEINPUT must be 32 bytes, got {ctypes.sizeof(MOUSEINPUT)}"
assert ctypes.sizeof(INPUT) == 40, f"INPUT must be 40 bytes, got {ctypes.sizeof(INPUT)}"
assert getattr(INPUT, "_u").offset == 8, f"INPUT union offset must be 8, got {getattr(INPUT, '_u').offset}"


# ---------------------------------------------------------------------------
# MouseDriver
# ---------------------------------------------------------------------------
class MouseDriver:
    """
    Win32 mouse controller providing physical human-like cursor glides,
    clicks, double clicks, dragging, scrolling, and instant interrupt aborts.
    """

    def __init__(
        self,
        config: Optional[MouseConfig] = None,
        kinematics: Optional[KinematicsEngine] = None,
        reticle_callback: Optional[Callable[[int, int, int], None]] = None,
        simulation_mode: bool = False,
        speed_factor: Optional[float] = None,
        preview_reticle_ms: Optional[int] = None,
    ):
        self.config = config or MouseConfig()
        self.kinematics = kinematics or KinematicsEngine(
            config=KinematicConfig(
                arc_deviation_ratio=0.14,
                jitter_amplitude_px=self.config.micro_jitter_amplitude_px,
                overshoot_distance_max=float(min(5, self.config.overshoot_radius_px)),
            )
        )
        self.reticle_callback = reticle_callback
        self.simulation_mode = simulation_mode
        self.speed_factor = speed_factor if speed_factor is not None else self.config.speed_factor
        self.preview_reticle_ms = (
            preview_reticle_ms if preview_reticle_ms is not None else self.config.preview_reticle_ms
        )

        # Internal state tracking
        self._held_buttons: Set[str] = set()
        self._sim_cursor_pos: Tuple[int, int] = (960, 540)
        self.simulation_history: List[Dict[str, Any]] = []

        self._init_win32()

    def _init_win32(self) -> None:
        try:
            self._user32 = ctypes.windll.user32
            self._winmm = ctypes.windll.winmm

            self._user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
            self._user32.SendInput.restype = wintypes.UINT

            self._user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
            self._user32.GetCursorPos.restype = wintypes.BOOL

            self._winmm.timeBeginPeriod.argtypes = [wintypes.UINT]
            self._winmm.timeBeginPeriod.restype = wintypes.UINT

            self._winmm.timeEndPeriod.argtypes = [wintypes.UINT]
            self._winmm.timeEndPeriod.restype = wintypes.UINT
        except Exception:
            pass

    def get_cursor_pos(self) -> Tuple[int, int]:
        """Returns current screen coordinates (x, y)."""
        if self.simulation_mode:
            return self._sim_cursor_pos

        pt = wintypes.POINT()
        if self._user32.GetCursorPos(ctypes.byref(pt)):
            return (pt.x, pt.y)
        return self._sim_cursor_pos

    def move_to(
        self,
        x: int,
        y: int,
        duration: Optional[float] = None,
        cancellation_token: Optional[threading.Event] = None,
        preview_reticle: bool = False,
    ) -> bool:
        """
        Executes human curved glide to (x, y) at 120Hz.
        Checks cancellation_token before and during movement.
        Aborts in < 2ms if set. Returns True if arrived, False if interrupted.
        """
        if cancellation_token and cancellation_token.is_set():
            self.release_all_buttons()
            return False

        if preview_reticle and self.preview_reticle_ms > 0:
            if self.reticle_callback:
                self.reticle_callback(x, y, self.preview_reticle_ms)
            if cancellation_token and cancellation_token.wait(timeout=self.preview_reticle_ms / 1000.0):
                self.release_all_buttons()
                return False

        start_pt = self.get_cursor_pos()
        if start_pt == (x, y):
            return True

        waypoints = self.kinematics.generate_trajectory(
            start_pt=start_pt,
            target_pt=(x, y),
            duration=duration,
            speed_factor=self.speed_factor,
        )

        step_delay_s = max(0.001, self.config.step_delay_ms / 1000.0)

        # High-resolution timer period activation
        try:
            self._winmm.timeBeginPeriod(1)
        except Exception:
            pass

        try:
            for pt in waypoints:
                if cancellation_token and cancellation_token.is_set():
                    self.release_all_buttons()
                    return False

                self._apply_cursor_move(pt[0], pt[1])

                if cancellation_token and cancellation_token.wait(timeout=step_delay_s):
                    self.release_all_buttons()
                    return False
        finally:
            try:
                self._winmm.timeEndPeriod(1)
            except Exception:
                pass

        return True

    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        clicks: int = 1,
        interval_ms: int = 60,
        cancellation_token: Optional[threading.Event] = None,
        preview_reticle: bool = True,
    ) -> bool:
        """
        Executes optional pre-click reticle preview (300ms), glides to target, and clicks.
        """
        if cancellation_token and cancellation_token.is_set():
            self.release_all_buttons()
            return False

        target_x = x if x is not None else self.get_cursor_pos()[0]
        target_y = y if y is not None else self.get_cursor_pos()[1]

        # 300ms Pre-click reticle preview
        if preview_reticle and self.preview_reticle_ms > 0:
            if self.reticle_callback:
                self.reticle_callback(target_x, target_y, self.preview_reticle_ms)
            if cancellation_token and cancellation_token.wait(timeout=self.preview_reticle_ms / 1000.0):
                self.release_all_buttons()
                return False

        if x is not None and y is not None:
            if not self.move_to(x, y, cancellation_token=cancellation_token, preview_reticle=False):
                return False

        for i in range(clicks):
            if cancellation_token and cancellation_token.is_set():
                self.release_all_buttons()
                return False

            if not self.mouse_down(button, cancellation_token=cancellation_token):
                return False

            # Dwell hold time
            dwell_s = 0.040
            if cancellation_token and cancellation_token.wait(timeout=dwell_s):
                self.release_all_buttons()
                return False

            if not self.mouse_up(button, cancellation_token=cancellation_token):
                return False

            if i < clicks - 1:
                int_s = max(0.010, interval_ms / 1000.0)
                if cancellation_token and cancellation_token.wait(timeout=int_s):
                    return False

        return True

    def double_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        cancellation_token: Optional[threading.Event] = None,
    ) -> bool:
        """Executes double click with realistic inter-click pause."""
        return self.click(
            x=x,
            y=y,
            button=button,
            clicks=2,
            interval_ms=80,
            cancellation_token=cancellation_token,
            preview_reticle=True,
        )

    def mouse_down(
        self,
        button: str = "left",
        cancellation_token: Optional[threading.Event] = None,
    ) -> bool:
        """Presses and holds the specified mouse button."""
        if cancellation_token and cancellation_token.is_set():
            return False

        flag_map = {
            "left": MOUSEEVENTF_LEFTDOWN,
            "right": MOUSEEVENTF_RIGHTDOWN,
            "middle": MOUSEEVENTF_MIDDLEDOWN,
        }
        flag = flag_map.get(button.lower(), MOUSEEVENTF_LEFTDOWN)

        if self.simulation_mode:
            self.simulation_history.append({"event": "mouse_down", "button": button, "pos": self._sim_cursor_pos})
        else:
            self._send_mouse_flag(flag)

        self._held_buttons.add(button.lower())
        return True

    def mouse_up(
        self,
        button: str = "left",
        cancellation_token: Optional[threading.Event] = None,
    ) -> bool:
        """Releases the specified mouse button."""
        flag_map = {
            "left": MOUSEEVENTF_LEFTUP,
            "right": MOUSEEVENTF_RIGHTUP,
            "middle": MOUSEEVENTF_MIDDLEUP,
        }
        flag = flag_map.get(button.lower(), MOUSEEVENTF_LEFTUP)

        if self.simulation_mode:
            self.simulation_history.append({"event": "mouse_up", "button": button, "pos": self._sim_cursor_pos})
        else:
            self._send_mouse_flag(flag)

        self._held_buttons.discard(button.lower())
        return True

    def drag_and_drop(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        button: str = "left",
        cancellation_token: Optional[threading.Event] = None,
    ) -> bool:
        """Glides to start, holds button, glides to destination, releases button."""
        if not self.move_to(start_x, start_y, cancellation_token=cancellation_token):
            return False

        if not self.mouse_down(button, cancellation_token=cancellation_token):
            return False

        # Brief pause before dragging
        if cancellation_token and cancellation_token.wait(timeout=0.060):
            self.release_all_buttons()
            return False

        if not self.move_to(end_x, end_y, cancellation_token=cancellation_token):
            self.release_all_buttons()
            return False

        # Brief pause before release
        if cancellation_token and cancellation_token.wait(timeout=0.040):
            self.release_all_buttons()
            return False

        return self.mouse_up(button, cancellation_token=cancellation_token)

    def scroll(
        self,
        delta: int,
        x: Optional[int] = None,
        y: Optional[int] = None,
        cancellation_token: Optional[threading.Event] = None,
    ) -> bool:
        """Emits vertical wheel scrolling."""
        if cancellation_token and cancellation_token.is_set():
            return False

        if x is not None and y is not None:
            if not self.move_to(x, y, cancellation_token=cancellation_token):
                return False

        raw_delta = delta * WHEEL_DELTA

        if self.simulation_mode:
            self.simulation_history.append({"event": "scroll", "delta": delta, "pos": self._sim_cursor_pos})
        else:
            inp = INPUT(type=INPUT_MOUSE)
            inp.u.mi.dx = 0
            inp.u.mi.dy = 0
            inp.u.mi.mouseData = wintypes.DWORD(raw_delta & 0xFFFFFFFF)
            inp.u.mi.dwFlags = MOUSEEVENTF_WHEEL
            inp.u.mi.time = 0
            inp.u.mi.dwExtraInfo = 0
            self._user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

        return True

    def release_all_buttons(self) -> None:
        """Emergency release of all currently tracked and physical mouse buttons."""
        if self.simulation_mode:
            self.simulation_history.append({"event": "release_all_buttons", "held": list(self._held_buttons)})
        else:
            self._send_mouse_flag(MOUSEEVENTF_LEFTUP | MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_MIDDLEUP)

        self._held_buttons.clear()

    # -----------------------------------------------------------------------
    # Low-level cursor dispatch helpers
    # -----------------------------------------------------------------------
    @staticmethod
    def normalize_coordinates(
        x: int,
        y: int,
        vx: int,
        vy: int,
        vcx: int,
        vcy: int,
    ) -> Tuple[int, int]:
        """
        Clamps (x, y) to virtual desktop [vx, vx + vcx - 1] and [vy, vy + vcy - 1],
        then normalizes to Win32 absolute [0, 65535] coordinate space.
        """
        clamped_x = max(vx, min(x, vx + vcx - 1))
        clamped_y = max(vy, min(y, vy + vcy - 1))
        norm_x = max(0, min(65535, int(((clamped_x - vx) * 65535) / max(1, vcx - 1))))
        norm_y = max(0, min(65535, int(((clamped_y - vy) * 65535) / max(1, vcy - 1))))
        return (norm_x, norm_y)

    def _apply_cursor_move(self, x: int, y: int) -> None:
        if self.simulation_mode:
            self._sim_cursor_pos = (x, y)
            self.simulation_history.append({"event": "move", "pos": (x, y)})
            return

        vx = self._user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = self._user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vcx = self._user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        vcy = self._user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

        if vcx <= 0:
            vcx = self._user32.GetSystemMetrics(SM_CXSCREEN)
        if vcy <= 0:
            vcy = self._user32.GetSystemMetrics(SM_CYSCREEN)

        # Normalize with virtual screen boundary clamping
        norm_x, norm_y = self.normalize_coordinates(x, y, vx, vy, vcx, vcy)

        inp = INPUT(type=INPUT_MOUSE)
        inp.u.mi.dx = norm_x
        inp.u.mi.dy = norm_y
        inp.u.mi.mouseData = 0
        inp.u.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        inp.u.mi.time = 0
        inp.u.mi.dwExtraInfo = 0

        self._user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _send_mouse_flag(self, flag: int) -> None:
        inp = INPUT(type=INPUT_MOUSE)
        inp.u.mi.dx = 0
        inp.u.mi.dy = 0
        inp.u.mi.mouseData = 0
        inp.u.mi.dwFlags = flag
        inp.u.mi.time = 0
        inp.u.mi.dwExtraInfo = 0
        self._user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
