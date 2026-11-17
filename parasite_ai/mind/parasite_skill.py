"""
parasite_ai/mind/parasite_skill.py - The Titular ParasiteSkill Symbiosis Orchestrator.

Drives the host's standalone "Gemini in Chrome" app window purely through physical
OS inputs (Alt+G, CF_DIB Monitor-1 screenshot paste, query paste, Enter, UIA-located
Copy button sentinel harvest) and strict nonce-bound protocol parsing. Operates in
proactive planning, reactive deadlock/oscillation recovery, and skill co-authoring
phases with fail-closed diagnostics, Discord alerting, circuit breaking, and
guaranteed clipboard/focus teardown.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Tuple
import numpy as np
from pydantic import BaseModel, Field

from parasite_ai.config import ParasiteSkillConfig
from parasite_ai.hands.clipboard import (
    ClipboardError,
    ClipboardLockedError,
    ClipboardSnapshot,
    DibPackError,
    IImageClipboard,
    Win32ImageClipboard,
)
from parasite_ai.mind.memory import ActionType, compute_dhash, hamming_distance
from parasite_ai.mind.offloader import (
    SentinelClipboardVerifier,
    Win32BrowserWindowBackend,
    sanitize_consultation_prompt,
)
from parasite_ai.mind.parasite_protocol import (
    ParasiteAction,
    ParasiteFailure,
    ParasitePhase,
    ParasitePlan,
    ParasiteRequest,
    build_parasite_prompt,
    generate_nonce,
    parse_response,
)
from parasite_ai.ui.bridge import EpisodeEvent

logger = logging.getLogger(__name__)

# Failures that do NOT count toward the circuit breaker (environmental/operator actions)
_NO_BREAKER_FAILURES = frozenset(
    {
        ParasiteFailure.PREFLIGHT_SENSITIVE_WINDOW,
        ParasiteFailure.BREAKER_OPEN,
        ParasiteFailure.BUDGET_EXHAUSTED,
        ParasiteFailure.HOTKEY_INTERRUPTED,
        ParasiteFailure.INTERRUPTED,
    }
)

# Failures that do NOT send a Discord alert (avoid spam or operator action)
_NO_ALERT_FAILURES = frozenset(
    {
        ParasiteFailure.BREAKER_OPEN,
        ParasiteFailure.BUDGET_EXHAUSTED,
        ParasiteFailure.HOTKEY_INTERRUPTED,
        ParasiteFailure.INTERRUPTED,
    }
)

# Failures that skip writing full diagnostic bundles
_LOG_ONLY_FAILURES = frozenset(
    {
        ParasiteFailure.BREAKER_OPEN,
        ParasiteFailure.BUDGET_EXHAUSTED,
    }
)


# ---------------------------------------------------------------------------
# Backend Protocols & Win32 / OS Discovery Implementations
# ---------------------------------------------------------------------------

class IGeminiWindowBackend(Protocol):
    """OS window & UIA interface scoped exclusively to the visible Gemini app window."""

    def get_foreground_hwnd(self) -> int: ...
    def get_process_name(self, hwnd: int) -> str: ...
    def get_window_title(self, hwnd: int) -> str: ...
    def get_window_rect(self, hwnd: int) -> Tuple[int, int, int, int]: ...
    def minimize_window(self, hwnd: int) -> bool: ...
    def focus_window(self, hwnd: int) -> bool: ...
    def ensure_on_primary_monitor(self, hwnd: int) -> bool: ...
    def has_input_focus(self, hwnd: int) -> bool: ...
    def find_uia_button(
        self, hwnd: int, names: List[str], pick_last: bool = True
    ) -> Optional[Tuple[int, int]]: ...


# Controls/titles treated as generic Chrome widget chrome eligible for UIA/local inspection
_GENERIC_CHROME_OVERLAY_TITLES = frozenset({"", "chrome", "google chrome"})

_GWL_STYLE = -16
_WS_MINIMIZEBOX = 0x00020000
_WM_CLOSE = 0x0010


class GeminiWindowBackend(Win32BrowserWindowBackend):
    """Production Win32 + read-only UIA backend extending Win32BrowserWindowBackend."""

    def get_foreground_hwnd(self) -> int:
        try:
            import ctypes

            return int(ctypes.windll.user32.GetForegroundWindow() or 0)
        except Exception:
            return 0

    def get_process_name(self, hwnd: int) -> str:
        if not hwnd:
            return ""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return ""
            h_proc = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h_proc:
                return ""
            try:
                buf = ctypes.create_unicode_buffer(512)
                sz = wintypes.DWORD(512)
                if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(sz)):
                    return os.path.basename(buf.value)
            finally:
                kernel32.CloseHandle(h_proc)
        except Exception:
            pass
        return ""

    def list_candidate_windows(self, process_names: List[str]) -> List[Dict[str, Any]]:
        """Lists visible non-minimized top-level windows matching allowed process names."""
        try:
            from parasite_ai.mind.verifier import get_live_windows

            allowed = {p.strip().lower() for p in process_names if p.strip()}
            candidates: List[Dict[str, Any]] = []
            for win in get_live_windows(include_empty_titles=True):
                if win.get("is_minimized"):
                    continue
                proc = str(win.get("process_name") or "").strip()
                if allowed and proc.lower() not in allowed:
                    continue
                rect = win.get("rect") or (0, 0, 0, 0)
                if (rect[2] - rect[0]) < 80 or (rect[3] - rect[1]) < 80:
                    continue
                candidates.append(win)
            return candidates
        except Exception as exc:
            logger.debug("list_candidate_windows skipped: %s", exc)
            return []

    def has_minimize_box(self, hwnd: int) -> bool:
        """True iff Win32 window style carries WS_MINIMIZEBOX."""
        if not hwnd:
            return True
        try:
            import ctypes

            style = int(ctypes.windll.user32.GetWindowLongW(hwnd, _GWL_STYLE))
            return bool(style & _WS_MINIMIZEBOX)
        except Exception:
            return True

    def is_window_visible_active(self, hwnd: int) -> bool:
        """True when hwnd exists, is visible, and is not minimized (IsIconic)."""
        if not hwnd:
            return False
        try:
            import ctypes

            u32 = ctypes.windll.user32
            return bool(u32.IsWindow(hwnd) and u32.IsWindowVisible(hwnd) and not u32.IsIconic(hwnd))
        except Exception:
            return False

    def minimize_window(self, hwnd: int) -> bool:
        if not hwnd:
            return False
        try:
            import ctypes

            return bool(ctypes.windll.user32.ShowWindow(hwnd, 6))  # SW_MINIMIZE
        except Exception:
            return False

    def dismiss_window(
        self, hwnd: int, toggle_hotkey_fn: Optional[Callable[[], bool]] = None
    ) -> bool:
        """
        Cleanly hides or dismisses the verified Gemini window/overlay:
        - Standard Chrome PWA windows with WS_MINIMIZEBOX use SW_MINIMIZE.
        - Borderless floating "Gemini in Chrome" widgets without WS_MINIMIZEBOX
          toggle closed via Alt+G (with WM_CLOSE fallback if still open).
        """
        if not hwnd:
            return False
        if not self.is_window_visible_active(hwnd):
            return True
        if self.has_minimize_box(hwnd):
            if self.minimize_window(hwnd):
                return True

        try:
            if toggle_hotkey_fn is not None:
                if self.get_foreground_hwnd() != hwnd:
                    self.focus_window(hwnd)
                    time.sleep(0.05)
                toggle_hotkey_fn()
                deadline = time.perf_counter() + 0.40
                while time.perf_counter() < deadline:
                    if not self.is_window_visible_active(hwnd):
                        return True
                    time.sleep(0.04)

            import ctypes

            if self.is_window_visible_active(hwnd):
                ctypes.windll.user32.PostMessageW(hwnd, _WM_CLOSE, 0, 0)
                time.sleep(0.10)
            return not self.is_window_visible_active(hwnd)
        except Exception as exc:
            logger.debug("GeminiWindowBackend.dismiss_window fallback minimize: %s", exc)
            return self.minimize_window(hwnd)

    def awaken_accessibility(self, hwnd: int) -> None:
        """
        Triggers lazy Chromium AXPlatformNodeWin DOM tree materialization by sending
        non-blocking WM_GETOBJECT (OBJID_CLIENT) to Chrome child render HWNDs and
        performing a lightweight read-only ControlFromPoint probe inside the client area.
        """
        if not hwnd:
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            targets: List[int] = [int(hwnd)]

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def _child_proc(ch_hwnd: int, _lparam: int) -> bool:
                if ch_hwnd:
                    targets.append(int(ch_hwnd))
                return True

            user32.EnumChildWindows(hwnd, WNDENUMPROC(_child_proc), 0)
            res = ctypes.c_size_t(0)
            # WM_GETOBJECT = 0x003D, OBJID_CLIENT = -4, SMTO_ABORTIFHUNG = 0x0002
            for th in targets[:16]:
                try:
                    user32.SendMessageTimeoutW(
                        wintypes.HWND(th),
                        0x003D,
                        wintypes.WPARAM(0),
                        wintypes.LPARAM(-4),
                        0x0002,
                        40,
                        ctypes.byref(res),
                    )
                except Exception:
                    pass
            oleacc = getattr(ctypes.windll, "oleacc", None)
            if oleacc is not None and hasattr(oleacc, "AccessibleObjectFromWindow"):
                class _GUID(ctypes.Structure):
                    _fields_ = [
                        ("Data1", wintypes.DWORD),
                        ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD),
                        ("Data4", ctypes.c_ubyte * 8),
                    ]

                iid_iunknown = _GUID(
                    0x00000000,
                    0x0000,
                    0x0000,
                    (ctypes.c_ubyte * 8)(0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46),
                )
                acc_ptr = ctypes.c_void_p()
                try:
                    oleacc.AccessibleObjectFromWindow(
                        wintypes.HWND(hwnd),
                        wintypes.DWORD(0xFFFFFFFC),
                        ctypes.byref(iid_iunknown),
                        ctypes.byref(acc_ptr),
                    )
                    if acc_ptr.value:
                        vtbl = ctypes.cast(
                            acc_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
                        ).contents
                        release_fn = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])
                        release_fn(acc_ptr)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            import uiautomation as auto

            l, t, r, b = self.get_window_rect(hwnd)
            if r - l >= 40 and b - t >= 40:
                cx = (l + r) // 2
                auto.ControlFromPoint(cx, (t + b) // 2)
                auto.ControlFromPoint(cx, t + int((b - t) * 0.82))
        except Exception:
            pass

    def has_input_focus(self, hwnd: int) -> bool:
        """Verifies keyboard caret via GUITHREADINFO or compact read-only UIA focused element."""
        if not hwnd:
            return False
        try:
            import ctypes
            from parasite_ai.mind.dual_mind import check_caret_focus

            tid = int(ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None) or 0)
            if tid and check_caret_focus(tid):
                return True
        except Exception:
            pass

        try:
            import ctypes
            from ctypes import wintypes
            import uiautomation as auto

            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            focused = auto.GetFocusedControl()
            if focused is not None:
                ctrl_type = str(getattr(focused, "ControlTypeName", "") or "")
                focused_pid = int(getattr(focused, "ProcessId", 0) or 0)
                if pid.value == 0 or focused_pid == pid.value:
                    if ctrl_type == "EditControl":
                        return True
                    if ctrl_type == "DocumentControl":
                        _, top, _, bottom = self.get_window_rect(hwnd)
                        win_h = bottom - top
                        rect = getattr(focused, "BoundingRectangle", None)
                        ctrl_h = (rect.height() if callable(getattr(rect, "height", None)) else getattr(rect, "height", 0)) if rect is not None else 0
                        # Reject outer full-window DocumentControl wrappers; accept compact composer docs only
                        if win_h <= 0 or (ctrl_h > 0 and ctrl_h < win_h * 0.5):
                            return True
        except Exception:
            pass
        return False

    def _iter_uia_controls(
        self, hwnd: int, max_nodes: int = 1200, max_depth: int = 14
    ) -> Iterable[Any]:
        """Bounded breadth-first traversal of read-only Win32 UIA subtree rooted at hwnd."""
        if not hwnd:
            return []
        try:
            self.awaken_accessibility(hwnd)
            import uiautomation as auto

            root = auto.ControlFromHandle(hwnd)
            if root is None:
                return []

            visited_controls: List[Any] = []
            queue: List[Tuple[Any, int]] = [(root, 0)]
            while queue and len(visited_controls) < max_nodes:
                ctrl, depth = queue.pop(0)
                visited_controls.append(ctrl)
                if depth < max_depth:
                    try:
                        for child in ctrl.GetChildren() or []:
                            queue.append((child, depth + 1))
                    except Exception:
                        pass
            return visited_controls
        except Exception as exc:
            logger.debug("GeminiWindowBackend._iter_uia_controls error: %s", exc)
            return []

    @staticmethod
    def _control_center(ctrl: Any) -> Optional[Tuple[int, int]]:
        rect = getattr(ctrl, "BoundingRectangle", None)
        if rect is not None and rect.width() > 0 and rect.height() > 0:
            return (int((rect.left + rect.right) // 2), int((rect.top + rect.bottom) // 2))
        return None

    def find_uia_text_match(
        self, hwnd: int, signatures: List[str], max_nodes: int = 250
    ) -> Optional[str]:
        """Checks read-only UIA control names/ids inside hwnd for Gemini overlay signatures."""
        if not hwnd or not signatures:
            return None
        needles = [s.strip().lower() for s in signatures if s.strip()]
        if not needles:
            return None
        for ctrl in self._iter_uia_controls(hwnd, max_nodes=max_nodes, max_depth=12):
            parts = [
                str(getattr(ctrl, "Name", "") or ""),
                str(getattr(ctrl, "AutomationId", "") or ""),
            ]
            combined = " ".join(p for p in parts if p).strip().lower()
            if not combined:
                continue
            for needle in needles:
                if needle in combined:
                    return needle
        return None

    def sample_uia_labels(self, hwnd: int, limit: int = 12) -> List[str]:
        """Collects non-empty UIA control labels for diagnostic receipts."""
        labels: List[str] = []
        for ctrl in self._iter_uia_controls(hwnd, max_nodes=200, max_depth=10):
            name = str(getattr(ctrl, "Name", "") or "").strip()
            ctype = str(getattr(ctrl, "ControlTypeName", "") or "").strip()
            if name:
                entry = f"{ctype}:{name[:60]}" if ctype else name[:60]
                if entry not in labels:
                    labels.append(entry)
                    if len(labels) >= limit:
                        break
        return labels

    def find_uia_input_center(
        self, hwnd: int, names: List[str]
    ) -> Optional[Tuple[int, int]]:
        """Finds composer EditControl/DocumentControl centroid via UIA inside hwnd."""
        if not hwnd:
            return None
        wanted = [n.strip().lower() for n in names if n.strip()]
        fallback_center: Optional[Tuple[int, int]] = None
        for ctrl in self._iter_uia_controls(hwnd, max_nodes=450, max_depth=14):
            ctype = str(getattr(ctrl, "ControlTypeName", "") or "")
            if ctype not in ("EditControl", "DocumentControl"):
                continue
            center = self._control_center(ctrl)
            if center is None:
                continue
            rect = getattr(ctrl, "BoundingRectangle", None)
            if rect is not None and (rect.width() < 20 or rect.height() < 12):
                continue
            cname = str(getattr(ctrl, "Name", "") or "").strip().lower()
            if wanted and any(w in cname for w in wanted):
                return center
            if fallback_center is None and ctype == "EditControl":
                fallback_center = center
        return fallback_center

    def find_uia_button(
        self, hwnd: int, names: List[str], pick_last: bool = True
    ) -> Optional[Tuple[int, int]]:
        """Finds button centroid strictly via read-only Win32 UIA tree walk on hwnd."""
        if not hwnd or not names:
            return None
        wanted = [n.strip().lower() for n in names if n.strip()]
        if not wanted:
            return None
        wanted_set = set(wanted)
        searching_copy = any("copy" in w for w in wanted)
        matches: List[Tuple[int, int]] = []
        for ctrl in self._iter_uia_controls(hwnd, max_nodes=1200, max_depth=14):
            ctype = str(getattr(ctrl, "ControlTypeName", "") or "")
            if ctype not in ("ButtonControl", "CustomControl", "MenuItemControl", "HyperlinkControl"):
                continue
            cname = str(getattr(ctrl, "Name", "") or "").strip().lower()
            caid = str(getattr(ctrl, "AutomationId", "") or "").strip().lower()
            combined = f"{cname} {caid}".strip()
            if not combined:
                continue
            if searching_copy and ("copy link" in combined or "copy prompt" in combined):
                continue
            matched = (
                cname in wanted_set
                or caid in wanted_set
                or any(len(w) >= 4 and w in combined for w in wanted)
            )
            if matched:
                center = self._control_center(ctrl)
                if center is not None:
                    matches.append(center)
        if not matches:
            return None
        return matches[-1] if pick_last else matches[0]


# ---------------------------------------------------------------------------
# Bounded Local Reasoning Assist (Tier 2 ScreenGrounder + Tier 3 Loaded VLM)
# ---------------------------------------------------------------------------

class ILocalAssistBackend(Protocol):
    """Scoped fallback reasoning strictly bounded to verified gemini_hwnd rect."""

    def verify_gemini_surface(
        self, hwnd: int, rect: Tuple[int, int, int, int], signatures: List[str]
    ) -> Tuple[bool, str]: ...

    def locate_input_box(
        self, hwnd: int, rect: Tuple[int, int, int, int], input_names: List[str]
    ) -> Optional[Tuple[int, int, str]]: ...

    def locate_send_button(
        self, hwnd: int, rect: Tuple[int, int, int, int], send_names: List[str]
    ) -> Optional[Tuple[int, int, str]]: ...

    def locate_copy_button(
        self,
        hwnd: int,
        rect: Tuple[int, int, int, int],
        copy_names: List[str],
        exclude_points: Optional[List[Tuple[int, int]]] = None,
    ) -> Optional[Tuple[int, int, str]]: ...


class HybridLocalAssistBackend:
    """
    Bounded local fallback inside verified Chrome Gemini overlay:
    1. Tier 2: ScreenGrounder (scoped UIA + RapidOCR, 0 MB extra GPU VRAM).
    2. Tier 3: Already-resident LocalBrainManager VLM strictly on window crop
       using native pixel parsing and zero numerical anchoring (§8.1-§8.3).
    """

    def __init__(
        self,
        screen_grounder: Any = None,
        brain_manager: Any = None,
        capturer: Any = None,
    ) -> None:
        self.screen_grounder = screen_grounder
        self.brain_manager = brain_manager
        self.capturer = capturer

    @staticmethod
    def _rect_contains(rect: Tuple[int, int, int, int], x: int, y: int) -> bool:
        l, t, r, b = rect
        return l <= x < r and t <= y < b

    @staticmethod
    def _crop_wh(rect: Tuple[int, int, int, int]) -> Optional[Tuple[int, int, int, int]]:
        l, t, r, b = rect
        w = r - l
        h = b - t
        if w < 40 or h < 40:
            return None
        return (l, t, w, h)

    def _grounder_elements_in_rect(
        self, hwnd: int, rect: Tuple[int, int, int, int], keywords: List[str]
    ) -> List[Any]:
        if self.screen_grounder is None or not hasattr(self.screen_grounder, "ground"):
            return []
        try:
            elems = self.screen_grounder.ground(
                window_filter=hwnd,
                force_ocr=True,
                goal_keywords=keywords or None,
                lazy=False,
            )
            return [
                e
                for e in (elems or [])
                if self._rect_contains(rect, int(getattr(e, "center_x", -1)), int(getattr(e, "center_y", -1)))
            ]
        except Exception as exc:
            logger.debug("HybridLocalAssistBackend.ScreenGrounder skipped: %s", exc)
            return []

    def _vlm_ready(self) -> bool:
        if self.brain_manager is None or self.capturer is None:
            return False
        if type(self.brain_manager).__name__ == "MagicMock":
            return False
        supports = getattr(self.brain_manager, "supports_vision", None)
        return bool(callable(supports) and supports())

    def _capture_crop(self, rect: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        wh = self._crop_wh(rect)
        if wh is None or self.capturer is None:
            return None
        try:
            crop = self.capturer.capture_rect(wh)
            if isinstance(crop, np.ndarray) and crop.size > 0 and crop.ndim >= 2:
                return crop
        except Exception as exc:
            logger.debug("HybridLocalAssistBackend crop capture error: %s", exc)
        return None

    @staticmethod
    def _pad_crop_for_vlm(
        crop: np.ndarray,
        min_tokens: int = 1024,
        patch_size: int = 28,
    ) -> np.ndarray:
        """
        Pads a small window crop at top-left origin (0, 0) with right/bottom black pixels
        so its dimensions are exact multiples of `patch_size` and >= `min_tokens` patches.
        This prevents llama-server (--image-min-tokens 1024) from internally upscaling the
        crop, preserving strict 1:1 native screen pixel coordinates inside [0..cw-1, 0..ch-1].
        """
        arr = np.asarray(crop)
        if arr.ndim == 2:
            arr = np.repeat(arr[:, :, None], 3, axis=2)
        elif arr.shape[2] >= 4:
            arr = arr[:, :, :3]
        ch, cw = arr.shape[:2]
        min_pixels = max(1, min_tokens) * patch_size * patch_size
        min_side = int(math.ceil(math.sqrt(min_pixels) / patch_size)) * patch_size
        pad_w = max(((cw + patch_size - 1) // patch_size) * patch_size, min_side)
        pad_h = max(((ch + patch_size - 1) // patch_size) * patch_size, min_side)
        if pad_w == cw and pad_h == ch:
            return np.ascontiguousarray(arr, dtype=np.uint8)
        canvas = np.zeros((pad_h, pad_w, 3), dtype=np.uint8)
        canvas[0:ch, 0:cw] = arr.astype(np.uint8, copy=False)
        return canvas

    def _ask_vlm_locate(
        self,
        rect: Tuple[int, int, int, int],
        target_description: str,
        reject_thought_substrings: Tuple[str, ...] = (),
        max_local_y: Optional[int] = None,
        exclude_points: Optional[List[Tuple[int, int]]] = None,
        snap_button_contour: bool = False,
    ) -> Optional[Tuple[int, int]]:
        if not self._vlm_ready():
            return None
        crop = self._capture_crop(rect)
        if crop is None:
            return None
        ch, cw = crop.shape[:2]
        if cw < 16 or ch < 16:
            return None
        try:
            from parasite_ai.vision.foveated import encode_image_to_data_uri

            vlm_crop = crop
            if exclude_points:
                vlm_crop = crop.copy()
                yy, xx = np.ogrid[:ch, :cw]
                for ex in exclude_points:
                    ex_lx = int(ex[0]) - rect[0]
                    ex_ly = int(ex[1]) - rect[1]
                    if -12 <= ex_lx < cw + 12 and -12 <= ex_ly < ch + 12:
                        mask = (xx - ex_lx) ** 2 + (yy - ex_ly) ** 2 <= 12 ** 2
                        vlm_crop[mask] = 0

            padded_crop = self._pad_crop_for_vlm(vlm_crop)
            padded_b64 = encode_image_to_data_uri(padded_crop, max_dim=1920, quality=90)

            # Symbolic-only instruction inside cropped window frame (§8.2 & §8.3 compliant; zero digits)
            crop_sys_prompt = (
                "You are a desktop GUI visual locator inspecting a cropped window screenshot.\n"
                "Emit one Thought line and one Action line using pixels relative to the top-left corner of the window:\n"
                "Thought: <brief visual observation>\n"
                "Action: click(start_box='(x, y)')\n"
                "If the exact requested control is not visible in the screenshot, emit Action: wait() instead.\n"
                "Never click a different control (such as Send or add-tabs) as a substitute, and never copy placeholder syntax."
            )
            goal = (
                f"Locate and click the control labeled '{target_description}' "
                "inside this cropped Gemini window screenshot using click(start_box='(x, y)'), "
                "or emit Action: wait() if it is absent."
            )
            if hasattr(self.brain_manager, "generate_cua_step"):
                thought, plan = self.brain_manager.generate_cua_step(
                    user_goal=goal,
                    screen_frame=vlm_crop,
                    image_base64=padded_b64 or None,
                    screen_width=cw,
                    screen_height=ch,
                    system_prompt=crop_sys_prompt,
                    max_tokens=128,
                    temperature=0.05,
                )
            else:
                return None

            if getattr(plan, "action", None) == ActionType.WAIT:
                return None

            if reject_thought_substrings:
                combined_thought = f"{thought or ''} {getattr(plan, 'reasoning', '') or ''}".lower()
                if any(bad in combined_thought for bad in reject_thought_substrings):
                    logger.debug(
                        "HybridLocalAssistBackend._ask_vlm_locate rejected contradicted VLM thought: %s",
                        combined_thought[:160],
                    )
                    return None

            coords = getattr(plan, "coordinates", None)
            if coords is None or len(coords) < 2:
                return None
            lx = int(coords[0])
            ly = int(coords[1])
            # Reject out-of-crop or border-clamped (cw-1 / ch-1) coordinates from padded margin
            if lx < 0 or lx >= cw - 1 or ly < 0 or ly >= ch - 1:
                return None
            if snap_button_contour and int(vlm_crop.max()) > int(vlm_crop.min()):
                try:
                    from parasite_ai.vision.grounding import CentroidSnapper

                    snapper = CentroidSnapper(max_button_size=64, edge_margin_px=28)
                    snap_res = snapper.snap_with_details(
                        lx, ly, frame=vlm_crop, frame_origin=(0, 0)
                    )
                    if snap_res.snapped:
                        sx = int(snap_res.x)
                        sy = int(snap_res.y)
                        snap_dist = math.hypot(sx - lx, sy - ly)
                        snap_screen_pt = (rect[0] + sx, rect[1] + sy)
                        if snap_dist <= 32.0 and not self._is_excluded(snap_screen_pt, exclude_points):
                            lx = sx
                            ly = sy
                except Exception as snap_exc:
                    logger.debug("CentroidSnapper fallback in _ask_vlm_locate: %s", snap_exc)
            if max_local_y is not None and ly >= max_local_y:
                logger.warning(
                    "HybridLocalAssistBackend._ask_vlm_locate rejected coordinate inside bottom composer strip (ly=%d >= max_local_y=%d).",
                    ly,
                    max_local_y,
                )
                return None
            # Clamp strictly inside safe interior margin of the verified window crop
            lx = max(4, min(cw - 5, lx))
            ly = max(4, min(ch - 5, ly))
            return (rect[0] + lx, rect[1] + ly)
        except Exception as exc:
            logger.debug("HybridLocalAssistBackend._ask_vlm_locate error: %s", exc)
            return None

    def _ask_vlm_surface(self, rect: Tuple[int, int, int, int]) -> bool:
        if not self._vlm_ready() or not hasattr(self.brain_manager, "generate"):
            return False
        crop = self._capture_crop(rect)
        if crop is None:
            return False
        try:
            from parasite_ai.vision.foveated import encode_image_to_data_uri

            b64_uri = encode_image_to_data_uri(crop, max_dim=1920, quality=85)
            raw = str(
                self.brain_manager.generate(
                    prompt=(
                        "Inspect this cropped desktop window. Does it display the Google Gemini "
                        "assistant overlay or chat interface? Reply strictly YES or NO."
                    ),
                    system_prompt="You are a visual window verifier. Reply ONLY YES or NO.",
                    max_tokens=12,
                    temperature=0.0,
                    image_base64=b64_uri,
                )
                or ""
            ).strip()
            has_yes = bool(re.search(r"\byes\b", raw, re.IGNORECASE))
            has_no = bool(re.search(r"\bno\b", raw, re.IGNORECASE))
            return has_yes and not has_no
        except Exception as exc:
            logger.debug("HybridLocalAssistBackend._ask_vlm_surface error: %s", exc)
            return False

    def verify_gemini_surface(
        self, hwnd: int, rect: Tuple[int, int, int, int], signatures: List[str]
    ) -> Tuple[bool, str]:
        needles = [s.strip().lower() for s in signatures if s.strip()]
        elems = self._grounder_elements_in_rect(hwnd, rect, signatures)
        for el in elems:
            lbl = str(getattr(el, "label", "") or "").strip().lower()
            if lbl and any(n in lbl for n in needles):
                return True, "screen_grounder"
        if self._ask_vlm_surface(rect):
            return True, "local_vlm"
        return False, "none"

    def locate_input_box(
        self, hwnd: int, rect: Tuple[int, int, int, int], input_names: List[str]
    ) -> Optional[Tuple[int, int, str]]:
        needles = [s.strip().lower() for s in input_names if s.strip()]
        elems = self._grounder_elements_in_rect(hwnd, rect, input_names)
        for el in elems:
            lbl = str(getattr(el, "label", "") or "").strip().lower()
            if lbl and any(n in lbl for n in needles):
                return (int(el.center_x), int(el.center_y), "screen_grounder")
        pt = self._ask_vlm_locate(rect, "Ask Gemini / Type @ to add tabs message input box")
        if pt is not None:
            return (pt[0], pt[1], "local_vlm")
        return None

    @staticmethod
    def _is_excluded(
        pt: Tuple[int, int],
        exclude_points: Optional[List[Tuple[int, int]]],
        min_dist_px: float = 16.0,
    ) -> bool:
        if not exclude_points:
            return False
        for ex in exclude_points:
            if math.hypot(pt[0] - ex[0], pt[1] - ex[1]) < min_dist_px:
                return True
        return False

    def locate_send_button(
        self,
        hwnd: int,
        rect: Tuple[int, int, int, int],
        send_names: List[str],
        exclude_points: Optional[List[Tuple[int, int]]] = None,
    ) -> Optional[Tuple[int, int, str]]:
        needles = [s.strip().lower() for s in send_names if s.strip()]
        elems = self._grounder_elements_in_rect(hwnd, rect, send_names)
        for el in elems:
            lbl = str(getattr(el, "label", "") or "").strip().lower()
            if (
                lbl
                and any(n in lbl for n in needles)
                and not self._is_excluded((int(el.center_x), int(el.center_y)), exclude_points)
            ):
                return (int(el.center_x), int(el.center_y), "screen_grounder")
        pt = self._ask_vlm_locate(
            rect,
            "blue circular Send message button with an up arrow inside the bottom prompt composer",
            exclude_points=exclude_points,
            snap_button_contour=True,
        )
        if pt is not None and not self._is_excluded(pt, exclude_points):
            return (pt[0], pt[1], "local_vlm")
        return None

    def locate_copy_button(
        self,
        hwnd: int,
        rect: Tuple[int, int, int, int],
        copy_names: List[str],
        exclude_points: Optional[List[Tuple[int, int]]] = None,
    ) -> Optional[Tuple[int, int, str]]:
        needles = [s.strip().lower() for s in copy_names if s.strip()]
        elems = self._grounder_elements_in_rect(hwnd, rect, copy_names)
        matches = [
            el
            for el in elems
            if (
                str(getattr(el, "label", "") or "").strip().lower() in needles
                or any(
                    len(n) >= 4
                    and n in str(getattr(el, "label", "") or "").strip().lower()
                    for n in needles
                )
            )
            and not self._is_excluded(
                (int(el.center_x), int(el.center_y)), exclude_points
            )
        ]
        if matches:
            chosen = matches[-1]
            return (int(chosen.center_x), int(chosen.center_y), "screen_grounder")
        rect_h = max(0, rect[3] - rect[1])
        max_local_y = (rect_h - 48) if rect_h >= 300 else None
        pt = self._ask_vlm_locate(
            rect,
            "Copy response icon button (two overlapping rectangles located in the small action icon row directly beneath the assistant reply text, to the right of the thumbs-up, thumbs-down, and regenerate icons)",
            reject_thought_substrings=(
                "send button",
                '"send"',
                "send message",
                "upward arrow",
                "up arrow",
                "to send",
                "add tabs",
                "more options",
                "microphone",
                "thumbs up",
                "thumbs down",
                "good response",
                "bad response",
                "add attachments",
                "attachment",
                "plus",
                "close",
            ),
            max_local_y=max_local_y,
            exclude_points=exclude_points,
            snap_button_contour=True,
        )
        if pt is not None and not self._is_excluded(pt, exclude_points):
            return (pt[0], pt[1], "local_vlm")
        return None

    def verify_hover_tooltip(
        self,
        rect: Tuple[int, int, int, int],
        cursor_pt: Optional[Tuple[int, int]] = None,
        require_positive: bool = True,
    ) -> Tuple[bool, str]:
        """Checks via local RapidOCR whether a hover tooltip near cursor_pt is a Copy control."""
        get_ocr = getattr(self.screen_grounder, "_get_ocr_engine", None)
        if not callable(get_ocr) or self.capturer is None:
            return (not require_positive), ""
        engine = get_ocr()
        if engine is None:
            return (not require_positive), ""
        crop = self._capture_crop(rect)
        if crop is None:
            return (not require_positive), ""
        try:
            from PIL import Image

            ch, cw = crop.shape[:2]
            if cursor_pt is not None:
                cx = max(0, min(cw - 1, int(cursor_pt[0]) - rect[0]))
                cy = max(0, min(ch - 1, int(cursor_pt[1]) - rect[1]))
                sx0 = max(0, cx - 140)
                sx1 = min(cw, cx + 140)
                sy0 = max(0, cy - 60)
                sy1 = min(ch, cy + 60)
                roi = crop[sy0:sy1, sx0:sx1]
            else:
                roi = crop
            rh, rw = roi.shape[:2]
            if rw < 16 or rh < 16:
                return (not require_positive), ""
            roi_2x = np.asarray(
                Image.fromarray(roi).resize((rw * 2, rh * 2), Image.Resampling.BICUBIC),
                dtype=np.uint8,
            )
            ocr_res = engine(roi_2x)
            boxes = ocr_res[0] if isinstance(ocr_res, tuple) else ocr_res
            if not boxes:
                return (not require_positive), ""
            texts = [str(item[1]) for item in boxes if len(item) >= 2 and item[1]]
            joined = " | ".join(texts)
            low = joined.lower()
            forbidden = (
                "close",
                "more options",
                "redo",
                "regenerate",
                "good response",
                "bad response",
                "thumbs",
                "dock",
                "pin",
                "new chat",
                "microphone",
                "add files",
                "upload",
            )
            if any(tok in low for tok in forbidden):
                return False, joined
            if require_positive and "copy" not in low:
                return False, joined
            return True, joined
        except Exception as exc:
            logger.debug("HybridLocalAssistBackend.verify_hover_tooltip error: %s", exc)
            return (not require_positive), ""


class IEnvironmentDiscovery(Protocol):
    """OS-only provider listing live open windows and installed programs (§7.3 / §8.4)."""

    def collect(
        self, max_programs: int = 40, max_windows: int = 15
    ) -> Tuple[List[str], List[str]]: ...


class Win32EnvironmentDiscovery:
    """
    Collects verified open top-level windows and installed Windows programs
    exclusively from OS APIs (Start Menu .lnk stems & Win32 App Paths registry).
    Never uses hardcoded app_map dictionaries (§7.3 / §8.4).
    """

    def __init__(
        self,
        window_guard: Any = None,
        shortcut_roots: Optional[List[Path]] = None,
        registry_names_fn: Optional[Callable[[], List[str]]] = None,
    ) -> None:
        self.window_guard = window_guard
        if shortcut_roots is not None:
            self._shortcut_roots = list(shortcut_roots)
        else:
            roots: List[Path] = []
            for env_var in ("ProgramData", "APPDATA"):
                base = os.environ.get(env_var)
                if base:
                    roots.append(Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
            self._shortcut_roots = roots
        self._registry_names_fn = registry_names_fn

    def _collect_open_windows(self, max_windows: int) -> List[str]:
        if max_windows <= 0:
            return []
        try:
            from parasite_ai.mind.verifier import get_live_windows

            results: List[str] = []
            for w in get_live_windows(include_empty_titles=False):
                if w.get("is_minimized"):
                    continue
                title = str(w.get("title") or "").strip()
                proc = str(w.get("process_name") or "").strip()
                hwnd = int(w.get("hwnd") or 0)
                if not title:
                    continue
                if self.window_guard and hasattr(self.window_guard, "evaluate_sensitivity"):
                    is_sens, _ = self.window_guard.evaluate_sensitivity(
                        title=title, process_name=proc, hwnd=hwnd
                    )
                    if is_sens:
                        continue
                safe_title = sanitize_consultation_prompt(title)[:72]
                entry = f"{proc}: {safe_title}" if proc else safe_title
                if entry not in results:
                    results.append(entry)
                if len(results) >= max_windows:
                    break
            return results
        except Exception as exc:
            logger.debug("Open-window discovery skipped: %s", exc)
            return []

    def _collect_start_menu_programs(self) -> List[str]:
        found: List[str] = []
        skip_prefixes = ("uninstall", "readme", "help", "manual", "documentation", "license")
        for root in self._shortcut_roots:
            if not root.exists():
                continue
            try:
                for lnk in root.rglob("*.lnk"):
                    stem = lnk.stem.strip()
                    if not stem or stem.lower().startswith(skip_prefixes):
                        continue
                    found.append(stem)
            except Exception:
                continue
        return found

    def _collect_registry_app_paths(self) -> List[str]:
        if self._registry_names_fn is not None:
            return list(self._registry_names_fn())
        names: List[str] = []
        try:
            import winreg

            subkey_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(hive, subkey_path) as key:
                        idx = 0
                        while True:
                            try:
                                sub = winreg.EnumKey(key, idx)
                                stem = Path(sub).stem.strip()
                                if stem:
                                    names.append(stem)
                                idx += 1
                            except OSError:
                                break
                except OSError:
                    continue
        except Exception:
            pass
        return names

    def collect(
        self, max_programs: int = 40, max_windows: int = 15
    ) -> Tuple[List[str], List[str]]:
        open_windows = self._collect_open_windows(max_windows)
        if max_programs <= 0:
            return open_windows, []

        dedup: dict[str, str] = {}
        for item in self._collect_start_menu_programs() + self._collect_registry_app_paths():
            clean = sanitize_consultation_prompt(item).strip()
            if not clean:
                continue
            key = clean.lower()
            if key not in dedup:
                dedup[key] = clean

        programs = sorted(dedup.values(), key=str.lower)[:max_programs]
        return open_windows, programs


# ---------------------------------------------------------------------------
# Invocation Result & Orchestrator
# ---------------------------------------------------------------------------

class ParasiteResult(BaseModel):
    """Structured outcome returned by ParasiteSkill.invoke()."""

    ok: bool
    phase: ParasitePhase
    plan: Optional[ParasitePlan] = None
    action: Optional[ParasiteAction] = None
    skill_markdown: Optional[str] = None
    parsed_skill: Optional[Any] = None
    failure: Optional[ParasiteFailure] = None
    detail: str = ""
    duration_sec: float = 0.0
    diagnostics_path: Optional[Path] = None
    identity_mode: str = "win32_title"
    rescued_by: Optional[str] = None
    submit_method: str = "enter"
    scroll_steps: int = 0


class ParasiteSkill:
    """Physical desktop symbiosis orchestrator for Gemini in Chrome."""

    def __init__(
        self,
        config: ParasiteSkillConfig,
        keyboard_driver: Any,
        mouse_driver: Any,
        capturer: Any,
        window_guard: Any = None,
        interrupt_guard: Any = None,
        bridge: Any = None,
        clipboard: Optional[IImageClipboard] = None,
        window_backend: Optional[IGeminiWindowBackend] = None,
        env_discovery: Optional[IEnvironmentDiscovery] = None,
        local_assist: Optional[ILocalAssistBackend] = None,
        clock: Callable[[], float] = time.perf_counter,
        sleep_fn: Optional[Callable[[float], None]] = None,
    ) -> None:
        self.config = config
        self.keyboard = keyboard_driver
        self.mouse = mouse_driver
        self.capturer = capturer
        self.window_guard = window_guard
        self.interrupt_guard = interrupt_guard
        self.bridge = bridge
        self.clipboard: IImageClipboard = (
            clipboard if clipboard is not None else Win32ImageClipboard()
        )
        self.window_backend: IGeminiWindowBackend = (
            window_backend if window_backend is not None else GeminiWindowBackend()
        )
        self.env_discovery: IEnvironmentDiscovery = (
            env_discovery
            if env_discovery is not None
            else Win32EnvironmentDiscovery(window_guard=window_guard)
        )
        self.local_assist = local_assist
        self._clock = clock
        self._sleep_fn = sleep_fn

        self._episode_invocations: int = 0
        self._consecutive_breaker_failures: int = 0
        self._breaker_open_until: float = 0.0

    def reset_episode_budget(self) -> None:
        """Resets per-episode invocation counter at episode start."""
        self._episode_invocations = 0

    def _is_breaker_open(self) -> bool:
        now = self._clock()
        if self._breaker_open_until <= 0.0:
            return False
        if now >= self._breaker_open_until:
            # Cooldown expired -> close circuit breaker cleanly
            self._breaker_open_until = 0.0
            self._consecutive_breaker_failures = 0
            return False
        return True

    def is_available(self) -> bool:
        """True iff ParasiteSkill is enabled and its circuit breaker is closed."""
        return bool(self.config.enabled) and not self._is_breaker_open()

    def _is_interrupted(self, cancellation_token: Optional[threading.Event]) -> bool:
        if cancellation_token is not None and cancellation_token.is_set():
            return True
        if self.interrupt_guard is not None and hasattr(self.interrupt_guard, "is_interrupted"):
            try:
                return bool(self.interrupt_guard.is_interrupted())
            except Exception:
                return False
        return False

    def _wait(
        self, seconds: float, cancellation_token: Optional[threading.Event]
    ) -> bool:
        """Waits cleanly; returns True immediately if cancelled."""
        if self._is_interrupted(cancellation_token):
            return True
        if seconds <= 0.0:
            return False
        if self._sleep_fn is not None:
            self._sleep_fn(seconds)
            return self._is_interrupted(cancellation_token)
        if cancellation_token is not None:
            return bool(cancellation_token.wait(timeout=seconds))
        time.sleep(seconds)
        return self._is_interrupted(cancellation_token)

    def _identity_matches(self, hwnd: int) -> Tuple[bool, str, str]:
        proc = (self.window_backend.get_process_name(hwnd) or "").strip()
        title = (self.window_backend.get_window_title(hwnd) or "").strip()
        proc_ok = not self.config.window_process_names or any(
            proc.lower() == p.lower() for p in self.config.window_process_names
        )
        title_ok = not self.config.window_title_keywords or any(
            kw.lower() in title.lower() for kw in self.config.window_title_keywords
        )
        return (proc_ok and title_ok), proc, title

    def verify_window_identity(
        self,
        hwnd: int,
        *,
        allow_uia: bool = True,
        allow_local_assist: bool = False,
    ) -> Tuple[bool, str, str, str]:
        """
        Verifies candidate hwnd via tiered identification:
        1. Win32 process + title keywords ("win32_title").
        2. Read-only UIA overlay signature match on untitled/generic Chrome popups ("uia_overlay").
        3. Bounded local ScreenGrounder/VLM surface verification ("local_assist:<tier>").
        """
        ok_win32, proc, title = self._identity_matches(hwnd)
        if ok_win32:
            return True, proc, title, "win32_title"

        proc_ok = not self.config.window_process_names or any(
            proc.lower() == p.lower() for p in self.config.window_process_names
        )
        if not proc_ok:
            return False, proc, title, "none"

        # Inspect generic/untitled Chrome widget surfaces without weakening titled tab guards
        if title.strip().lower() not in _GENERIC_CHROME_OVERLAY_TITLES:
            return False, proc, title, "none"

        if allow_uia:
            uia_fn = getattr(self.window_backend, "find_uia_text_match", None)
            if callable(uia_fn) and self.config.overlay_uia_signatures:
                matched_sig = uia_fn(hwnd, self.config.overlay_uia_signatures)
                if matched_sig:
                    return True, proc, title, "uia_overlay"

        if allow_local_assist and self.config.local_assist_enabled and self.local_assist is not None:
            rect = self.window_backend.get_window_rect(hwnd)
            ok_assist, tier = self.local_assist.verify_gemini_surface(
                hwnd, rect, self.config.overlay_uia_signatures
            )
            if ok_assist:
                return True, proc, title, f"local_assist:{tier}"

        return False, proc, title, "none"

    def _press_pagedown(
        self,
        cancellation_token: Optional[Any] = None,
        win_rect: Optional[Tuple[int, int, int, int]] = None,
    ) -> bool:
        """Scrolls down inside the Gemini pane (wheel + PageDown fallback)."""
        scrolled = False
        if win_rect is not None and callable(getattr(self.mouse, "scroll", None)):
            left, top, right, bottom = win_rect
            pane_x = left + max(1, (right - left) // 2)
            pane_y = top + max(1, int((bottom - top) * 0.40))
            try:
                res = self.mouse.scroll(-5, x=pane_x, y=pane_y, cancellation_token=cancellation_token)
                scrolled = True if res is None else bool(res)
            except TypeError:
                try:
                    res = self.mouse.scroll(-5, x=pane_x, y=pane_y)
                    scrolled = True if res is None else bool(res)
                except Exception:
                    pass
            except Exception:
                pass
        if callable(getattr(self.keyboard, "hotkey", None)):
            try:
                try:
                    res = self.keyboard.hotkey("pagedown", cancellation_token=cancellation_token)
                except TypeError:
                    res = self.keyboard.hotkey("pagedown")
            except Exception:
                return scrolled
            return True if (res is None or res or scrolled) else False
        if callable(getattr(self.keyboard, "press_hotkey", None)):
            try:
                res = self.keyboard.press_hotkey(["pagedown"])
            except Exception:
                return scrolled
            return True if (res is None or res or scrolled) else False
        return scrolled

    def _list_candidate_hwnds(self) -> List[int]:
        list_fn = getattr(self.window_backend, "list_candidate_windows", None)
        if not callable(list_fn):
            return []
        try:
            wins = list_fn(self.config.window_process_names)
            return [int(w["hwnd"]) for w in wins if w.get("hwnd")]
        except Exception:
            return []

    def _find_chrome_host_hwnd(self) -> int:
        """Finds an existing Chrome host window to restore/focus before retrying Alt+G."""
        allowed = {p.lower() for p in self.config.window_process_names}
        for hwnd in self._list_candidate_hwnds():
            try:
                proc, _title = self.window_backend.get_window_info(hwnd)
                if (proc or "").strip().lower() in allowed:
                    return hwnd
            except Exception:
                continue
        return 0

    def _find_open_gemini_window(self) -> Optional[Tuple[int, str, str, str]]:
        """Finds an already-visible Chrome Gemini window/overlay to avoid Alt+G toggle-close."""
        for hwnd in self._list_candidate_hwnds():
            ok_id, proc, title, mode = self.verify_window_identity(
                hwnd, allow_uia=True, allow_local_assist=False
            )
            if ok_id:
                return (hwnd, proc, title, mode)
        return None

    def _safe_capture_monitor1(self) -> Optional[np.ndarray]:
        """Captures Monitor 1 only if desktop sensitivity guard passes (fail-closed privacy)."""
        if self.window_guard and hasattr(self.window_guard, "is_safe_to_operate"):
            try:
                if not self.window_guard.is_safe_to_operate():
                    return None
            except Exception:
                return None
        try:
            frame = self.capturer.capture_screen(monitor_idx=1)
            if isinstance(frame, np.ndarray) and frame.size > 0:
                return frame
        except Exception:
            pass
        return None

    def resolve_gemini_window(
        self,
        *,
        prior_hwnd: int,
        transitions: List[str],
        cancellation_token: Optional[threading.Event] = None,
        allow_local_assist: bool = True,
    ) -> Tuple[int, str, str, str, Optional[ParasiteFailure], str]:
        """
        Prevents Alt+G toggle-close when overlay is already visible, dispatches Alt+G when needed,
        and verifies target window identity via Win32 -> UIA -> bounded local assist.
        Returns (gemini_hwnd, proc, title, identity_mode, failure_or_None, detail).
        """
        transitions.append("FOCUSING")
        pre_existing = self._find_open_gemini_window()
        if pre_existing is not None:
            ex_hwnd, ex_proc, ex_title, ex_mode = pre_existing
            if self.window_backend.get_foreground_hwnd() == ex_hwnd:
                transitions.append("VERIFYING_WINDOW")
                return ex_hwnd, ex_proc, ex_title, ex_mode, None, "Reused active Gemini window."
            if self.window_backend.focus_window(ex_hwnd):
                wait_dl = self._clock() + min(0.8, self.config.focus_timeout_sec)
                while self._clock() < wait_dl:
                    if self._is_interrupted(cancellation_token):
                        return 0, "", "", "none", ParasiteFailure.INTERRUPTED, "Interrupted focusing open Gemini window."
                    if self.window_backend.get_foreground_hwnd() == ex_hwnd:
                        transitions.append("VERIFYING_WINDOW")
                        return ex_hwnd, ex_proc, ex_title, ex_mode, None, "Focused existing Gemini overlay."
                    if self._wait(0.05, cancellation_token):
                        return 0, "", "", "none", ParasiteFailure.INTERRUPTED, "Cancelled focusing open Gemini window."

        pre_hotkey_hwnds = set(self._list_candidate_hwnds())
        hk_ok = self.keyboard.hotkey(*self.config.hotkey, cancellation_token=cancellation_token)
        if self._is_interrupted(cancellation_token):
            return 0, "", "", "none", ParasiteFailure.INTERRUPTED, "Interrupted during Alt+G hotkey."
        if not hk_ok:
            return (
                0,
                "",
                "",
                "none",
                ParasiteFailure.HOTKEY_INTERRUPTED,
                f"Focus hotkey {self.config.hotkey} did not complete.",
            )

        transitions.append("VERIFYING_WINDOW")
        poll_s = min(0.05, self.config.poll_interval_ms / 1000.0)
        last_candidate = 0
        last_proc, last_title = "", ""
        assist_calls = 0
        chrome_retried = False

        def _poll_until(deadline: float) -> Optional[Tuple[int, str, str, str, Optional[ParasiteFailure], str]]:
            nonlocal last_candidate, last_proc, last_title, assist_calls
            while True:
                if self._is_interrupted(cancellation_token):
                    return 0, "", "", "none", ParasiteFailure.INTERRUPTED, "Interrupted while waiting for Gemini focus."

                fg = self.window_backend.get_foreground_hwnd()
                if fg and fg != prior_hwnd:
                    last_candidate = fg
                    ok_id, last_proc, last_title, mode = self.verify_window_identity(
                        fg, allow_uia=True, allow_local_assist=False
                    )
                    if ok_id:
                        return fg, last_proc, last_title, mode, None, "Verified foreground Gemini window."

                # Detect newly spawned Chrome overlay windows even if OS delayed foreground switch
                if pre_hotkey_hwnds is not None:
                    post_hwnds = self._list_candidate_hwnds()
                    for cand in post_hwnds:
                        if cand not in pre_hotkey_hwnds and cand != prior_hwnd:
                            last_candidate = cand
                            ok_id, last_proc, last_title, mode = self.verify_window_identity(
                                cand, allow_uia=True, allow_local_assist=False
                            )
                            if ok_id:
                                self.window_backend.focus_window(cand)
                                return cand, last_proc, last_title, mode, None, "Verified spawned Gemini overlay."

                if self._clock() >= deadline:
                    return None

                if self._wait(poll_s, cancellation_token):
                    return 0, "", "", "none", ParasiteFailure.INTERRUPTED, "Cancelled waiting for focus."

        res = _poll_until(self._clock() + self.config.focus_timeout_sec)
        if res is not None:
            return res

        # Bounded 1-time recovery: if Alt+G produced no foreground transition (last_candidate == 0),
        # focus/restore an existing Chrome host window and retry Alt+G once before failing closed.
        if (not last_candidate or last_candidate == prior_hwnd) and not chrome_retried:
            chrome_retried = True
            chrome_hwnd = self._find_chrome_host_hwnd()
            if chrome_hwnd and self.window_backend.focus_window(chrome_hwnd):
                if self._wait(0.25, cancellation_token):
                    return 0, "", "", "none", ParasiteFailure.INTERRUPTED, "Cancelled during Chrome focus retry."
                pre_hotkey_hwnds = set(self._list_candidate_hwnds())
                hk2_ok = self.keyboard.hotkey(*self.config.hotkey, cancellation_token=cancellation_token)
                if self._is_interrupted(cancellation_token):
                    return 0, "", "", "none", ParasiteFailure.INTERRUPTED, "Interrupted during Alt+G retry."
                if hk2_ok:
                    res2 = _poll_until(self._clock() + min(2.5, self.config.focus_timeout_sec))
                    if res2 is not None:
                        return res2

        # Final bounded local-assist surface check on untitled candidate from allowed host process
        if (
            allow_local_assist
            and assist_calls < self.config.max_local_assist_calls_per_invoke
            and last_candidate
            and last_candidate != prior_hwnd
        ):
            assist_calls += 1
            ok_assist, c_proc, c_title, mode = self.verify_window_identity(
                last_candidate, allow_uia=False, allow_local_assist=True
            )
            if ok_assist:
                self.window_backend.focus_window(last_candidate)
                return last_candidate, c_proc, c_title, mode, None, "Verified Gemini overlay via local assist."
            last_proc, last_title = c_proc, c_title

        if last_candidate and last_candidate != prior_hwnd:
            return (
                last_candidate,
                last_proc,
                last_title,
                "none",
                ParasiteFailure.WINDOW_IDENTITY_MISMATCH,
                f"Foreground window mismatch after Alt+G: proc='{last_proc}', title='{last_title}'.",
            )
        return (
            0,
            "",
            "",
            "none",
            ParasiteFailure.FOCUS_TIMEOUT,
            "Timed out waiting for Gemini window foreground transition.",
        )

    @staticmethod
    def _frame_diff_score(
        frame_a: Optional[np.ndarray], frame_b: Optional[np.ndarray]
    ) -> float:
        """Computes mean absolute pixel difference between two same-shaped frames."""
        if (
            not isinstance(frame_a, np.ndarray)
            or not isinstance(frame_b, np.ndarray)
            or frame_a.size == 0
            or frame_b.size == 0
            or frame_a.shape != frame_b.shape
        ):
            return 0.0
        return float(np.mean(np.abs(frame_a.astype(np.float32) - frame_b.astype(np.float32))))

    def _write_diagnostics(
        self,
        *,
        phase: ParasitePhase,
        failure: ParasiteFailure,
        detail: str,
        nonce: str,
        trigger: Optional[str],
        transitions: List[str],
        gemini_hwnd: int = 0,
        prior_hwnd: int = 0,
        harvested_preview: str = "",
        failure_frame: Optional[np.ndarray] = None,
        identity_mode: str = "win32_title",
        rescued_by: Optional[str] = None,
        submit_method: str = "enter",
        scroll_steps: int = 0,
    ) -> Optional[Path]:
        if failure in _LOG_ONLY_FAILURES:
            return None
        try:
            from parasite_ai import __version__ as _app_version

            diag_dir = Path(self.config.diagnostics_dir)
            diag_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
            diag_path = diag_dir / f"{ts}_{phase.value}_{failure.value}.json"
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "app_version": _app_version,
                "artifact_role": "historical_forensic_debug_only",
                "coding_spec_prohibited": True,
                "phase": phase.value,
                "trigger": trigger,
                "nonce": nonce,
                "failure": failure.value,
                "detail": sanitize_consultation_prompt(detail),
                "transitions": transitions,
                "prior_hwnd": prior_hwnd,
                "gemini_hwnd": gemini_hwnd,
                "identity_mode": identity_mode,
                "rescued_by": rescued_by,
                "submit_method": submit_method,
                "scroll_steps": scroll_steps,
                "harvested_preview": sanitize_consultation_prompt(harvested_preview)[:4096],
            }
            if self.config.save_failure_frames and isinstance(failure_frame, np.ndarray) and failure_frame.size > 0:
                from PIL import Image

                img_path = diag_dir / f"{ts}_{phase.value}_{failure.value}.png"
                Image.fromarray(failure_frame).save(img_path)
                payload["failure_frame_path"] = str(img_path)

            diag_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self._rotate_diagnostics(diag_dir, keep=40)
            return diag_path
        except Exception as exc:
            logger.debug("Diagnostics write failed: %s", exc)
            return None

    def _rotate_diagnostics(self, diag_dir: Path, keep: int = 40) -> None:
        files = sorted(diag_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        excess = len(files) - keep
        for old in files[: max(0, excess)]:
            try:
                old.unlink()
            except OSError:
                pass

    def reset_circuit_breaker(self) -> None:
        """Manually resets the ParasiteSkill circuit breaker cooldown (e.g. on operator Parasite It)."""
        self._consecutive_breaker_failures = 0
        self._breaker_open_until = 0.0

    def _fail(
        self,
        *,
        start_time: float,
        phase: ParasitePhase,
        user_goal: str,
        failure: ParasiteFailure,
        detail: str,
        nonce: str,
        trigger: Optional[str],
        transitions: List[str],
        gemini_hwnd: int = 0,
        prior_hwnd: int = 0,
        harvested_preview: str = "",
        failure_frame: Optional[np.ndarray] = None,
        identity_mode: str = "win32_title",
        rescued_by: Optional[str] = None,
        submit_method: str = "enter",
        scroll_steps: int = 0,
    ) -> ParasiteResult:
        if failure not in _NO_BREAKER_FAILURES:
            self._consecutive_breaker_failures += 1
            logger.warning(
                "ParasiteSkill failure (%s): %s [streak=%d/%d]",
                failure.value,
                detail[:200],
                self._consecutive_breaker_failures,
                self.config.breaker_failure_threshold,
            )
            if self._consecutive_breaker_failures >= self.config.breaker_failure_threshold:
                self._breaker_open_until = self._clock() + self.config.breaker_cooldown_sec
                logger.warning(
                    "ParasiteSkill circuit breaker tripped open for %.1fs (%d consecutive failures; last=%s).",
                    self.config.breaker_cooldown_sec,
                    self._consecutive_breaker_failures,
                    failure.value,
                )

        diag_path = self._write_diagnostics(
            phase=phase,
            failure=failure,
            detail=detail,
            nonce=nonce,
            trigger=trigger,
            transitions=transitions,
            gemini_hwnd=gemini_hwnd,
            prior_hwnd=prior_hwnd,
            harvested_preview=harvested_preview,
            failure_frame=failure_frame,
            identity_mode=identity_mode,
            rescued_by=rescued_by,
            submit_method=submit_method,
            scroll_steps=scroll_steps,
        )

        if failure not in _NO_ALERT_FAILURES and self.bridge is not None and hasattr(
            self.bridge, "notify_episode_event"
        ):
            try:
                self.bridge.notify_episode_event(
                    EpisodeEvent(
                        kind="parasite_skill_alert",
                        goal=user_goal,
                        step=0,
                        data={
                            "failure": failure.value,
                            "phase": phase.value,
                            "detail": detail,
                            "diagnostics_path": str(diag_path) if diag_path else "",
                            "fallback": "LOCAL_UITARS",
                        },
                    )
                )
            except Exception as exc:
                logger.debug("Discord alert emission failed: %s", exc)

        return ParasiteResult(
            ok=False,
            phase=phase,
            failure=failure,
            detail=detail,
            duration_sec=max(0.0, self._clock() - start_time),
            diagnostics_path=diag_path,
            identity_mode=identity_mode,
            rescued_by=rescued_by,
            submit_method=submit_method,
            scroll_steps=scroll_steps,
        )

    def _teardown(
        self,
        *,
        clip_snap: Optional[ClipboardSnapshot],
        gemini_hwnd: int,
        minimize_gemini: bool,
        prior_hwnd: int,
        restore_prior_focus: bool,
        clear_draft: bool = False,
    ) -> None:
        if clip_snap is not None:
            try:
                self.clipboard.restore(clip_snap)
            except Exception as exc:
                logger.error("Teardown clipboard restore error: %s", exc)
        if clear_draft and gemini_hwnd:
            try:
                self.keyboard.hotkey("ctrl", "a")
                self.keyboard.hotkey("backspace")
                self.keyboard.hotkey("backspace")
            except Exception as exc:
                logger.debug("Teardown draft clear error: %s", exc)
        if minimize_gemini and gemini_hwnd:
            try:
                dismiss_fn = getattr(self.window_backend, "dismiss_window", None)
                if callable(dismiss_fn):
                    dismiss_fn(
                        gemini_hwnd,
                        toggle_hotkey_fn=lambda: self.keyboard.hotkey(*self.config.hotkey),
                    )
                else:
                    self.window_backend.minimize_window(gemini_hwnd)
            except Exception as exc:
                logger.debug("Teardown dismiss/minimize error: %s", exc)
        if restore_prior_focus and prior_hwnd and prior_hwnd != gemini_hwnd:
            try:
                self.window_backend.focus_window(prior_hwnd)
            except Exception as exc:
                logger.debug("Teardown prior focus restore error: %s", exc)
        if (minimize_gemini or restore_prior_focus) and gemini_hwnd:
            try:
                fg_after = self.window_backend.get_foreground_hwnd()
                if fg_after == gemini_hwnd:
                    self.window_backend.minimize_window(gemini_hwnd)
                    sleep_fn = getattr(self, "_sleep", None)
                    if callable(sleep_fn):
                        sleep_fn(0.15)
            except Exception as exc:
                logger.debug("Teardown post-restore gemini minimize error: %s", exc)

    def invoke(
        self,
        request: ParasiteRequest,
        cancellation_token: Optional[threading.Event] = None,
    ) -> ParasiteResult:
        """Executes the fail-closed physical Gemini Web symbiosis state machine. Never raises."""
        start_time = self._clock()
        nonce = generate_nonce()
        transitions: List[str] = ["PREFLIGHT"]
        trigger_str = request.trigger.value if request.trigger else None

        clip_snap: Optional[ClipboardSnapshot] = None
        desktop_frame: Optional[np.ndarray] = None
        prior_hwnd = 0
        gemini_hwnd = 0
        gemini_verified = False
        touched_foreground = False
        suppress_unknown_minimize = False
        identity_mode = "win32_title"
        rescued_by: Optional[str] = None
        submit_method = "enter"
        scroll_steps = 0
        draft_dirty = False

        def abort(
            failure: ParasiteFailure,
            detail: str,
            harvested_preview: str = "",
            failure_frame: Optional[np.ndarray] = None,
        ) -> ParasiteResult:
            diag_img = failure_frame
            if (
                diag_img is None
                and self.config.save_failure_frames
                and failure not in _LOG_ONLY_FAILURES
                and failure != ParasiteFailure.PREFLIGHT_SENSITIVE_WINDOW
            ):
                if gemini_hwnd and gemini_verified:
                    try:
                        wr = self.window_backend.get_window_rect(gemini_hwnd)
                        rwh = (
                            wr[0],
                            wr[1],
                            max(1, wr[2] - wr[0]),
                            max(1, wr[3] - wr[1]),
                        )
                        snap = self.capturer.capture_rect(rwh)
                        if isinstance(snap, np.ndarray) and snap.size > 0:
                            diag_img = snap
                    except Exception:
                        pass
                if diag_img is None:
                    diag_img = self._safe_capture_monitor1()
                    if diag_img is None:
                        diag_img = desktop_frame
            return self._fail(
                start_time=start_time,
                phase=request.phase,
                user_goal=request.user_goal,
                failure=failure,
                detail=detail,
                nonce=nonce,
                trigger=trigger_str,
                transitions=transitions,
                gemini_hwnd=gemini_hwnd,
                prior_hwnd=prior_hwnd,
                harvested_preview=harvested_preview,
                failure_frame=diag_img,
                identity_mode=identity_mode,
                rescued_by=rescued_by,
                submit_method=submit_method,
                scroll_steps=scroll_steps,
            )

        try:
            # --- Step 0: Preflight ---
            if self._is_interrupted(cancellation_token):
                return abort(ParasiteFailure.INTERRUPTED, "Cancelled prior to preflight.")
            if not self.config.enabled or self._is_breaker_open():
                return abort(
                    ParasiteFailure.BREAKER_OPEN,
                    "ParasiteSkill disabled or circuit breaker currently open.",
                )
            if self._episode_invocations >= self.config.max_invocations_per_episode:
                return abort(
                    ParasiteFailure.BUDGET_EXHAUSTED,
                    f"Episode invocation budget ({self.config.max_invocations_per_episode}) exhausted.",
                )
            if self.window_guard and hasattr(self.window_guard, "is_safe_to_operate"):
                if not self.window_guard.is_safe_to_operate():
                    return abort(
                        ParasiteFailure.PREFLIGHT_SENSITIVE_WINDOW,
                        "Sensitive window active on desktop; blocking cloud transfer.",
                    )

            self._episode_invocations += 1

            # Populate verified OS environment context when planning/recovering
            effective_req = request
            if (
                request.phase in (ParasitePhase.PROACTIVE_PLAN, ParasitePhase.REACTIVE_RECOVERY)
                and not request.open_windows
                and not request.available_programs
            ):
                open_wins, avail_progs = self.env_discovery.collect(
                    max_programs=self.config.max_discovered_programs
                )
                effective_req = request.model_copy(
                    update={"open_windows": open_wins, "available_programs": avail_progs}
                )

            # --- Step 1: Capture Target Monitor 1 BEFORE Alt+G (Q6) ---
            if effective_req.include_screenshot:
                transitions.append("CAPTURING")
                try:
                    desktop_frame = self.capturer.capture_screen(monitor_idx=1)
                except Exception as exc:
                    return abort(ParasiteFailure.CAPTURE_FAILED, f"Monitor-1 capture error: {exc}")
                if (
                    not isinstance(desktop_frame, np.ndarray)
                    or desktop_frame.size == 0
                ):
                    return abort(
                        ParasiteFailure.CAPTURE_FAILED,
                        "Target Monitor 1 screenshot empty or invalid.",
                    )

            # --- Step 2, 3 & 4: Resolve / Focus Gemini Window (toggle-safe + UIA/local assist) ---
            prior_hwnd = self.window_backend.get_foreground_hwnd()
            touched_foreground = True
            assist_calls_used = 0

            res_hwnd, _, _, identity_mode, resolve_fail, resolve_detail = self.resolve_gemini_window(
                prior_hwnd=prior_hwnd,
                transitions=transitions,
                cancellation_token=cancellation_token,
                allow_local_assist=self.config.local_assist_enabled,
            )
            if resolve_fail is not None:
                if resolve_fail == ParasiteFailure.WINDOW_IDENTITY_MISMATCH:
                    suppress_unknown_minimize = True
                diag_frame = desktop_frame
                if desktop_frame is not None and resolve_fail != ParasiteFailure.INTERRUPTED:
                    fresh_frame = self._safe_capture_monitor1()
                    if fresh_frame is not None:
                        diag_frame = fresh_frame
                return abort(
                    resolve_fail,
                    resolve_detail,
                    failure_frame=diag_frame,
                )

            gemini_hwnd = res_hwnd
            gemini_verified = True
            if identity_mode != "win32_title":
                rescued_by = identity_mode

            # --- Step 5: Verify Caret / UIA Input Focus (bounded UIA/local assist before fail-closed) ---
            caret_deadline = self._clock() + min(1.0, self.config.focus_timeout_sec / 2.0)
            caret_ok = False
            while True:
                if self._is_interrupted(cancellation_token):
                    return abort(ParasiteFailure.INTERRUPTED, "Interrupted verifying input caret.")
                if self.window_backend.has_input_focus(gemini_hwnd):
                    caret_ok = True
                    break
                if self._clock() >= caret_deadline:
                    break
                if self._wait(0.05, cancellation_token):
                    return abort(ParasiteFailure.INTERRUPTED, "Cancelled verifying caret.")

            if not caret_ok:
                win_rect_caret = self.window_backend.get_window_rect(gemini_hwnd)
                input_pt: Optional[Tuple[int, int]] = None
                input_src = ""
                uia_input_fn = getattr(self.window_backend, "find_uia_input_center", None)
                if callable(uia_input_fn):
                    uia_pt = uia_input_fn(gemini_hwnd, self.config.input_box_names)
                    if uia_pt is not None:
                        input_pt = uia_pt
                        input_src = "uia_input_click"

                if (
                    input_pt is None
                    and self.config.local_assist_enabled
                    and self.local_assist is not None
                    and assist_calls_used < self.config.max_local_assist_calls_per_invoke
                ):
                    assist_calls_used += 1
                    loc = self.local_assist.locate_input_box(
                        gemini_hwnd, win_rect_caret, self.config.input_box_names
                    )
                    if loc is not None:
                        input_pt = (loc[0], loc[1])
                        input_src = f"composer:{loc[2]}"

                if input_pt is not None:
                    rl, rt, rr, rb = win_rect_caret
                    if rl <= input_pt[0] < rr and rt <= input_pt[1] < rb:
                        self.mouse.click(
                            x=input_pt[0],
                            y=input_pt[1],
                            button="left",
                            clicks=1,
                            cancellation_token=cancellation_token,
                        )
                        if self._wait(0.15, cancellation_token):
                            return abort(ParasiteFailure.INTERRUPTED, "Cancelled during composer focus assist.")
                        if self.window_backend.has_input_focus(gemini_hwnd) or (
                            self.window_backend.get_foreground_hwnd() == gemini_hwnd
                        ):
                            caret_ok = True
                            rescued_by = rescued_by or input_src

            if not caret_ok:
                return abort(
                    ParasiteFailure.CARET_NOT_ACQUIRED,
                    "Gemini input caret/focus not acquired after Alt+G (fail-closed, zero blind clicks).",
                    failure_frame=desktop_frame,
                )

            # --- Step 6: Snapshot Clipboard & Paste CF_DIB Image ---
            transitions.append("PASTING_IMAGE")
            try:
                clip_snap = self.clipboard.snapshot()
            except ClipboardLockedError as exc:
                return abort(ParasiteFailure.CLIPBOARD_LOCKED, str(exc))

            if desktop_frame is not None:
                try:
                    self.clipboard.set_image_dib(desktop_frame)
                except DibPackError as exc:
                    return abort(ParasiteFailure.DIB_PACK_FAILED, str(exc))
                except ClipboardLockedError as exc:
                    return abort(ParasiteFailure.CLIPBOARD_LOCKED, str(exc))
                except ClipboardError as exc:
                    return abort(ParasiteFailure.DIB_PACK_FAILED, str(exc))

                win_rect = self.window_backend.get_window_rect(gemini_hwnd)
                rect_wh = (
                    win_rect[0],
                    win_rect[1],
                    max(1, win_rect[2] - win_rect[0]),
                    max(1, win_rect[3] - win_rect[1]),
                )
                pre_attach_dhash = compute_dhash(self.capturer.capture_rect(rect_wh))

                if identity_mode != "win32_title":
                    self.keyboard.hotkey("ctrl", "a", cancellation_token=cancellation_token)
                    self.keyboard.hotkey("backspace", cancellation_token=cancellation_token)
                    self.keyboard.hotkey("backspace", cancellation_token=cancellation_token)
                    if self._wait(0.10, cancellation_token):
                        return abort(
                            ParasiteFailure.INTERRUPTED,
                            "Interrupted clearing leftover composer draft.",
                        )

                draft_dirty = True
                paste_img_ok = self.keyboard.hotkey(
                    "ctrl", "v", cancellation_token=cancellation_token
                )
                if self._is_interrupted(cancellation_token):
                    return abort(ParasiteFailure.INTERRUPTED, "Interrupted during image paste.")
                if not paste_img_ok:
                    return abort(ParasiteFailure.PASTE_INTERRUPTED, "Ctrl+V image paste aborted.")

                settle_deadline = self._clock() + (self.config.attach_settle_ms / 1000.0)
                saw_attach_diff = False
                stable_attach_ticks = 0
                prev_attach_dhash = pre_attach_dhash
                while self._clock() < settle_deadline:
                    if self._wait(0.15, cancellation_token):
                        return abort(ParasiteFailure.INTERRUPTED, "Interrupted during attach settle.")
                    cur_dhash = compute_dhash(self.capturer.capture_rect(rect_wh))
                    if cur_dhash != pre_attach_dhash:
                        saw_attach_diff = True
                    if saw_attach_diff:
                        if cur_dhash == prev_attach_dhash:
                            stable_attach_ticks += 1
                            if stable_attach_ticks >= 2:
                                break
                        else:
                            stable_attach_ticks = 0
                    prev_attach_dhash = cur_dhash

            # --- Step 7: Paste Sanitized Query ---
            transitions.append("PASTING_QUERY")
            prompt = build_parasite_prompt(effective_req, nonce)
            try:
                self.clipboard.set_unicode_text(prompt)
            except ClipboardLockedError as exc:
                return abort(ParasiteFailure.CLIPBOARD_LOCKED, str(exc))

            draft_dirty = True
            paste_txt_ok = self.keyboard.hotkey(
                "ctrl", "v", cancellation_token=cancellation_token
            )
            if self._is_interrupted(cancellation_token):
                return abort(ParasiteFailure.INTERRUPTED, "Interrupted during query paste.")
            if not paste_txt_ok:
                return abort(ParasiteFailure.PASTE_INTERRUPTED, "Ctrl+V query paste aborted.")
            if self._wait(0.20, cancellation_token):
                return abort(ParasiteFailure.INTERRUPTED, "Interrupted settling pasted query.")

            # --- Step 8: Submit via Enter + Verified Send-Button Fallback ---
            transitions.append("SUBMITTING")
            win_rect = self.window_backend.get_window_rect(gemini_hwnd)
            rect_wh = (
                win_rect[0],
                win_rect[1],
                max(1, win_rect[2] - win_rect[0]),
                max(1, win_rect[3] - win_rect[1]),
            )
            pre_submit_frame = self.capturer.capture_rect(rect_wh)
            pre_submit_dhash = compute_dhash(pre_submit_frame)

            sub_ok = self.keyboard.hotkey("enter", cancellation_token=cancellation_token)
            if self._is_interrupted(cancellation_token):
                return abort(ParasiteFailure.INTERRUPTED, "Interrupted during Enter submit.")
            if not sub_ok:
                return abort(ParasiteFailure.SUBMIT_INTERRUPTED, "Enter submission aborted.")

            last_send_pos: Optional[Tuple[int, int]] = None
            send_uia_pos = self.window_backend.find_uia_button(
                gemini_hwnd, self.config.send_button_names, pick_last=True
            )
            locate_send_fn = (
                getattr(self.local_assist, "locate_send_button", None)
                if (self.config.local_assist_enabled and self.local_assist is not None)
                else None
            )
            if send_uia_pos is not None or callable(locate_send_fn):
                verify_deadline = self._clock() + self.config.submit_verify_timeout_sec
                enter_transitioned = False
                if self._wait(0.20, cancellation_token):
                    return abort(ParasiteFailure.INTERRUPTED, "Interrupted verifying submission.")
                post_enter_frame = self.capturer.capture_rect(rect_wh)
                post_enter_dhash = compute_dhash(post_enter_frame)
                if self._frame_diff_score(post_enter_frame, pre_submit_frame) >= 15.0:
                    enter_transitioned = True
                else:
                    while self._clock() < verify_deadline:
                        if self._wait(0.20, cancellation_token):
                            return abort(
                                ParasiteFailure.INTERRUPTED, "Interrupted verifying submission."
                            )
                        cur_sub_frame = self.capturer.capture_rect(rect_wh)
                        cur_sub_dhash = compute_dhash(cur_sub_frame)
                        sub_hd = (
                            hamming_distance(cur_sub_dhash, post_enter_dhash)
                            if (cur_sub_dhash is not None and post_enter_dhash is not None)
                            else 0
                        )
                        sub_step_diff = self._frame_diff_score(cur_sub_frame, post_enter_frame)
                        sub_total_diff = self._frame_diff_score(cur_sub_frame, pre_submit_frame)
                        if (sub_hd >= 4 and sub_step_diff >= 2.5) or sub_total_diff >= 15.0:
                            enter_transitioned = True
                            pre_submit_frame = cur_sub_frame
                            pre_submit_dhash = cur_sub_dhash
                            break

                if enter_transitioned:
                    draft_dirty = False

                if not enter_transitioned:
                    tried_send_points: List[Tuple[int, int]] = []
                    for send_attempt in range(2):
                        send_target: Optional[Tuple[int, int]] = self.window_backend.find_uia_button(
                            gemini_hwnd, self.config.send_button_names, pick_last=True
                        )
                        if send_target is not None and any(
                            math.hypot(send_target[0] - ex[0], send_target[1] - ex[1]) < 16.0
                            for ex in tried_send_points
                        ):
                            send_target = None
                        send_src = "send_button:uia"
                        if send_target is None and callable(locate_send_fn):
                            try:
                                loc_send = locate_send_fn(
                                    gemini_hwnd,
                                    win_rect,
                                    self.config.send_button_names,
                                    exclude_points=tried_send_points or None,
                                )
                            except TypeError:
                                loc_send = locate_send_fn(
                                    gemini_hwnd, win_rect, self.config.send_button_names
                                )
                            if loc_send is not None:
                                send_target = (int(loc_send[0]), int(loc_send[1]))
                                send_src = f"send_button:{loc_send[2]}"

                        if send_target is None:
                            break
                        rl, rt, rr, rb = win_rect
                        if not (rl <= send_target[0] < rr and rt <= send_target[1] < rb):
                            break

                        pre_click_frame = self.capturer.capture_rect(rect_wh)
                        pre_click_dhash = compute_dhash(pre_click_frame)

                        clicked_send = self.mouse.click(
                            x=send_target[0],
                            y=send_target[1],
                            button="left",
                            clicks=1,
                            cancellation_token=cancellation_token,
                        )
                        if self._is_interrupted(cancellation_token):
                            return abort(
                                ParasiteFailure.INTERRUPTED,
                                "Interrupted clicking Send button.",
                            )
                        if not clicked_send:
                            break

                        last_send_pos = (send_target[0], send_target[1])
                        submit_method = send_src
                        rescued_by = rescued_by or send_src
                        draft_dirty = False

                        click_verify_deadline = self._clock() + min(
                            1.0, self.config.submit_verify_timeout_sec
                        )
                        click_transitioned = False
                        while self._clock() < click_verify_deadline:
                            if self._wait(0.25, cancellation_token):
                                return abort(
                                    ParasiteFailure.INTERRUPTED,
                                    "Interrupted after Send button click.",
                                )
                            cur_click_frame = self.capturer.capture_rect(rect_wh)
                            cur_click_dhash = compute_dhash(cur_click_frame)
                            sub_hd = (
                                hamming_distance(cur_click_dhash, pre_click_dhash)
                                if (
                                    cur_click_dhash is not None
                                    and pre_click_dhash is not None
                                )
                                else 0
                            )
                            sub_step_diff = self._frame_diff_score(
                                cur_click_frame, pre_click_frame
                            )
                            sub_total_diff = self._frame_diff_score(
                                cur_click_frame, pre_submit_frame
                            )
                            if (sub_hd >= 4 and sub_step_diff >= 2.5) or sub_total_diff >= 15.0:
                                click_transitioned = True
                                pre_submit_frame = cur_click_frame
                                pre_submit_dhash = cur_click_dhash
                                break
                        if click_transitioned or send_attempt >= 1:
                            break
                        tried_send_points.append(last_send_pos)

            # --- Step 9: Await Generation Completion (UIA Copy + !Stop + Generation Activity Gate) ---
            transitions.append("AWAITING_GENERATION")
            gen_start = self._clock()
            gen_deadline = gen_start + self.config.generation_timeout_sec
            gen_poll_s = self.config.poll_interval_ms / 1000.0
            win_rect = self.window_backend.get_window_rect(gemini_hwnd)
            rect_wh = (
                win_rect[0],
                win_rect[1],
                max(1, win_rect[2] - win_rect[0]),
                max(1, win_rect[3] - win_rect[1]),
            )
            last_frame = self.capturer.capture_rect(rect_wh)
            last_dhash = compute_dhash(last_frame)
            stable_since = gen_start
            assist_copy_pos: Optional[Tuple[int, int]] = None
            generation_activity_observed = False
            scrolled_since_activity = False

            while True:
                if self._is_interrupted(cancellation_token):
                    return abort(ParasiteFailure.INTERRUPTED, "Interrupted awaiting generation.")

                now = self._clock()
                cur_frame = self.capturer.capture_rect(rect_wh)
                cur_dhash = compute_dhash(cur_frame)
                step_hd = (
                    hamming_distance(cur_dhash, last_dhash)
                    if (cur_dhash is not None and last_dhash is not None)
                    else 0
                )
                pre_hd = (
                    hamming_distance(cur_dhash, pre_submit_dhash)
                    if (cur_dhash is not None and pre_submit_dhash is not None)
                    else 0
                )
                frame_step_diff = self._frame_diff_score(cur_frame, last_frame)
                frame_total_diff = self._frame_diff_score(cur_frame, pre_submit_frame)
                if (
                    (last_dhash is None and cur_dhash is not None)
                    or (step_hd >= 3 and frame_step_diff >= 0.4)
                    or frame_step_diff >= 1.2
                ):
                    last_dhash = cur_dhash
                    last_frame = cur_frame
                    stable_since = now
                    generation_activity_observed = True
                    scrolled_since_activity = False
                elif pre_hd >= 3 or frame_total_diff >= 2.5:
                    generation_activity_observed = True

                stop_pos = self.window_backend.find_uia_button(
                    gemini_hwnd, self.config.stop_button_names, pick_last=True
                )
                if stop_pos is not None:
                    generation_activity_observed = True
                if generation_activity_observed:
                    draft_dirty = False
                copy_pos = self.window_backend.find_uia_button(
                    gemini_hwnd, self.config.copy_button_names, pick_last=True
                )
                if copy_pos is not None and last_send_pos is not None:
                    if math.hypot(copy_pos[0] - last_send_pos[0], copy_pos[1] - last_send_pos[1]) < 40.0:
                        copy_pos = None

                stable_ms = (now - stable_since) * 1000.0
                elapsed_gen_ms = (now - gen_start) * 1000.0
                if copy_pos is not None and stop_pos is None and stable_ms >= self.config.stream_stability_ms:
                    break

                max_pass_scrolls = max(12, self.config.scroll_before_copy_attempts * 4)
                max_total_scrolls = max(24, self.config.scroll_before_copy_attempts * 8)
                gen_gate_ready = elapsed_gen_ms >= self.config.min_generation_wait_ms and (
                    generation_activity_observed
                    or elapsed_gen_ms >= max(self.config.min_generation_wait_ms, 4000)
                )

                if (
                    copy_pos is None
                    and stop_pos is None
                    and stable_ms >= self.config.stream_stability_ms
                    and gen_gate_ready
                    and not scrolled_since_activity
                    and scroll_steps < max_total_scrolls
                    and callable(getattr(self.mouse, "scroll", None))
                ):
                    chat_cx = (win_rect[0] + win_rect[2]) // 2
                    chat_cy = win_rect[1] + int((win_rect[3] - win_rect[1]) * 0.45)
                    window_scrolls = 0
                    no_change_streak = 0
                    revealed_copy: Optional[Tuple[int, int]] = None
                    while (
                        window_scrolls < max_pass_scrolls
                        and scroll_steps < max_total_scrolls
                    ):
                        did_scroll = self.mouse.scroll(
                            self.config.scroll_wheel_delta,
                            x=chat_cx,
                            y=chat_cy,
                            cancellation_token=cancellation_token,
                        )
                        if self._is_interrupted(cancellation_token):
                            return abort(
                                ParasiteFailure.INTERRUPTED,
                                "Interrupted scrolling Gemini response.",
                            )
                        if not did_scroll:
                            break
                        scroll_steps += 1
                        window_scrolls += 1
                        if self._wait(0.25, cancellation_token):
                            return abort(
                                ParasiteFailure.INTERRUPTED,
                                "Interrupted settling after scroll.",
                            )
                        sc_frame = self.capturer.capture_rect(rect_wh)
                        sc_dhash = compute_dhash(sc_frame)
                        sc_diff = self._frame_diff_score(sc_frame, last_frame)
                        sc_hd = (
                            hamming_distance(sc_dhash, last_dhash)
                            if (sc_dhash is not None and last_dhash is not None)
                            else 0
                        )
                        if (sc_hd >= 3 and sc_diff >= 0.4) or sc_diff >= 0.8:
                            no_change_streak = 0
                            last_frame = sc_frame
                            last_dhash = sc_dhash
                            cand_copy = self.window_backend.find_uia_button(
                                gemini_hwnd, self.config.copy_button_names, pick_last=True
                            )
                            if cand_copy is not None and (
                                last_send_pos is None
                                or math.hypot(
                                    cand_copy[0] - last_send_pos[0],
                                    cand_copy[1] - last_send_pos[1],
                                )
                                >= 40.0
                            ):
                                revealed_copy = cand_copy
                                break
                        else:
                            no_change_streak += 1
                            if no_change_streak >= 2:
                                break
                    scrolled_since_activity = True
                    if revealed_copy is not None:
                        copy_pos = revealed_copy
                        break
                    # Keyboard Page_Down fallback when wheel scroll stalls before reaching bottom action row
                    if (
                        no_change_streak >= 2
                        and self._press_pagedown(cancellation_token)
                    ):
                        try:
                            scroll_steps += 1
                            window_scrolls += 1
                            if self._wait(0.35, cancellation_token):
                                return abort(
                                    ParasiteFailure.INTERRUPTED,
                                    "Interrupted settling after pagedown scroll.",
                                )
                            pd_frame = self.capturer.capture_rect(rect_wh)
                            pd_diff = self._frame_diff_score(pd_frame, last_frame)
                            if pd_diff >= 0.4:
                                last_frame = pd_frame
                                last_dhash = compute_dhash(pd_frame)
                                stable_since = self._clock()
                                scrolled_since_activity = False
                                cand_copy = self.window_backend.find_uia_button(
                                    gemini_hwnd, self.config.copy_button_names, pick_last=True
                                )
                                if cand_copy is not None and (
                                    last_send_pos is None
                                    or math.hypot(
                                        cand_copy[0] - last_send_pos[0],
                                        cand_copy[1] - last_send_pos[1],
                                    )
                                    >= 40.0
                                ):
                                    copy_pos = cand_copy
                                    break
                                continue
                        except Exception:
                            pass
                    if window_scrolls > 0:
                        if self._wait(0.50, cancellation_token):
                            return abort(
                                ParasiteFailure.INTERRUPTED,
                                "Interrupted settling animations after scroll.",
                            )
                        settle_frame = self.capturer.capture_rect(rect_wh)
                        settle_dhash = compute_dhash(settle_frame)
                        settle_diff = self._frame_diff_score(settle_frame, last_frame)
                        settle_hd = (
                            hamming_distance(settle_dhash, last_dhash)
                            if (settle_dhash is not None and last_dhash is not None)
                            else 0
                        )
                        if (settle_hd >= 3 and settle_diff >= 0.4) or settle_diff >= 1.2:
                            last_frame = settle_frame
                            last_dhash = settle_dhash
                            stable_since = self._clock()
                            continue

                if (
                    copy_pos is None
                    and stop_pos is None
                    and stable_ms >= self.config.stream_stability_ms
                    and gen_gate_ready
                    and self.config.local_assist_enabled
                    and self.local_assist is not None
                    and assist_calls_used < self.config.max_local_assist_calls_per_invoke
                ):
                    assist_calls_used += 1
                    excl = [last_send_pos] if last_send_pos is not None else None
                    try:
                        loc = self.local_assist.locate_copy_button(
                            gemini_hwnd,
                            win_rect,
                            self.config.copy_button_names,
                            exclude_points=excl,
                        )
                    except TypeError:
                        loc = self.local_assist.locate_copy_button(
                            gemini_hwnd, win_rect, self.config.copy_button_names
                        )
                    if loc is not None:
                        lx, ly, copy_tier = loc
                        rl, rt, rr, rb = win_rect
                        far_from_send = (
                            last_send_pos is None
                            or math.hypot(lx - last_send_pos[0], ly - last_send_pos[1]) >= 40.0
                        )
                        if rl <= lx < rr and rt <= ly < rb and far_from_send:
                            assist_copy_pos = (lx, ly)
                            rescued_by = rescued_by or f"copy:{copy_tier}"
                            break
                    stable_since = self._clock()
                    scrolled_since_activity = False

                if now >= gen_deadline:
                    gemini_snap = None
                    try:
                        gemini_snap = self.capturer.capture_rect(rect_wh)
                    except Exception:
                        pass
                    return abort(
                        ParasiteFailure.GENERATION_TIMEOUT,
                        f"Generation incomplete after {self.config.generation_timeout_sec}s.",
                        failure_frame=gemini_snap,
                    )

                if self._wait(gen_poll_s, cancellation_token):
                    return abort(ParasiteFailure.INTERRUPTED, "Cancelled during generation poll.")

            # --- Step 10: Harvest via UIA / Bounded Assist Copy Button + SentinelClipboardVerifier ---
            transitions.append("HARVESTING")
            failed_copy_points: List[Tuple[int, int]] = []
            if last_send_pos is not None:
                failed_copy_points.append(last_send_pos)

            copy_center = (
                self.window_backend.find_uia_button(
                    gemini_hwnd, self.config.copy_button_names, pick_last=True
                )
                or assist_copy_pos
            )
            if copy_center is not None and last_send_pos is not None:
                if math.hypot(copy_center[0] - last_send_pos[0], copy_center[1] - last_send_pos[1]) < 40.0:
                    copy_center = assist_copy_pos

            if copy_center is None and (
                self.config.local_assist_enabled
                and self.local_assist is not None
                and assist_calls_used < self.config.max_local_assist_calls_per_invoke
            ):
                if self._press_pagedown(cancellation_token):
                    scroll_steps += 1
                    if self._wait(0.35, cancellation_token):
                        return abort(
                            ParasiteFailure.INTERRUPTED,
                            "Interrupted settling after Step 10 pagedown scroll.",
                        )
                uia_after_scroll = self.window_backend.find_uia_button(
                    gemini_hwnd, self.config.copy_button_names, pick_last=True
                )
                if uia_after_scroll is not None and (
                    last_send_pos is None
                    or math.hypot(
                        uia_after_scroll[0] - last_send_pos[0],
                        uia_after_scroll[1] - last_send_pos[1],
                    )
                    >= 40.0
                ):
                    copy_center = uia_after_scroll
                elif assist_calls_used < self.config.max_local_assist_calls_per_invoke:
                    assist_calls_used += 1
                    excl_pts = list(failed_copy_points) or None
                    try:
                        loc = self.local_assist.locate_copy_button(
                            gemini_hwnd,
                            win_rect,
                            self.config.copy_button_names,
                            exclude_points=excl_pts,
                        )
                    except TypeError:
                        loc = self.local_assist.locate_copy_button(
                            gemini_hwnd, win_rect, self.config.copy_button_names
                        )
                    if loc is not None:
                        lx, ly, copy_tier = loc
                        rl, rt, rr, rb = win_rect
                        far_from_excl = all(
                            math.hypot(lx - ex[0], ly - ex[1]) >= 16.0
                            for ex in failed_copy_points
                        )
                        if rl <= lx < rr and rt <= ly < rb and far_from_excl:
                            copy_center = (lx, ly)
                            rescued_by = rescued_by or f"copy:{copy_tier}"

            if copy_center is None:
                return abort(
                    ParasiteFailure.COPY_BUTTON_NOT_FOUND,
                    "Native Copy button vanished from UIA tree prior to click.",
                )

            verifier = SentinelClipboardVerifier(
                clipboard=self.clipboard,
                poll_interval_s=0.05,
                default_timeout_s=self.config.harvest_timeout_sec,
            )

            harvested: Optional[str] = None
            max_harvest_attempts = 1 + max(
                0,
                self.config.max_local_assist_calls_per_invoke - assist_calls_used,
            )
            for _harvest_attempt in range(max_harvest_attempts):
                if copy_center is None:
                    break
                active_copy_pt = copy_center
                uia_live_copy = self.window_backend.find_uia_button(
                    gemini_hwnd, self.config.copy_button_names, pick_last=True
                )
                is_uia_pt = uia_live_copy is not None and (
                    last_send_pos is None
                    or math.hypot(
                        uia_live_copy[0] - last_send_pos[0],
                        uia_live_copy[1] - last_send_pos[1],
                    )
                    >= 40.0
                )
                if (
                    not is_uia_pt
                    and callable(getattr(self.mouse, "move_to", None))
                    and self.config.local_assist_enabled
                    and self.local_assist is not None
                    and callable(getattr(self.local_assist, "verify_hover_tooltip", None))
                ):
                    self.mouse.move_to(
                        active_copy_pt[0],
                        active_copy_pt[1],
                        cancellation_token=cancellation_token,
                    )
                    if self._is_interrupted(cancellation_token):
                        return abort(
                            ParasiteFailure.INTERRUPTED,
                            "Interrupted hovering Copy candidate.",
                        )
                    if self._wait(0.60, cancellation_token):
                        return abort(
                            ParasiteFailure.INTERRUPTED,
                            "Interrupted waiting for hover tooltip.",
                        )
                    try:
                        ok_tip, tip_text = self.local_assist.verify_hover_tooltip(
                            win_rect, cursor_pt=active_copy_pt
                        )
                    except TypeError:
                        ok_tip, tip_text = self.local_assist.verify_hover_tooltip(win_rect)
                    if not ok_tip:
                        logger.warning(
                            "Step 10 hover-tooltip guard aborted click at (%d, %d): tooltip=%r",
                            active_copy_pt[0],
                            active_copy_pt[1],
                            tip_text,
                        )
                        if active_copy_pt not in failed_copy_points:
                            failed_copy_points.append(active_copy_pt)
                        copy_center = None
                        saw_plan_tail = "</parasite_plan>" in str(tip_text or "").lower()
                        if saw_plan_tail and self._press_pagedown(cancellation_token, win_rect=win_rect):
                            scroll_steps += 1
                            if self._wait(0.35, cancellation_token):
                                return abort(
                                    ParasiteFailure.INTERRUPTED,
                                    "Interrupted settling after hover-guard pagedown scroll.",
                                )
                            uia_scrolled = self.window_backend.find_uia_button(
                                gemini_hwnd, self.config.copy_button_names, pick_last=True
                            )
                            if uia_scrolled is not None and (
                                last_send_pos is None
                                or math.hypot(
                                    uia_scrolled[0] - last_send_pos[0],
                                    uia_scrolled[1] - last_send_pos[1],
                                )
                                >= 40.0
                            ):
                                copy_center = uia_scrolled
                                continue
                        if assist_calls_used < self.config.max_local_assist_calls_per_invoke:
                            assist_calls_used += 1
                            try:
                                loc = self.local_assist.locate_copy_button(
                                    gemini_hwnd,
                                    win_rect,
                                    self.config.copy_button_names,
                                    exclude_points=list(failed_copy_points),
                                )
                            except TypeError:
                                loc = self.local_assist.locate_copy_button(
                                    gemini_hwnd, win_rect, self.config.copy_button_names
                                )
                            if (
                                loc is None
                                and not saw_plan_tail
                                and assist_calls_used < self.config.max_local_assist_calls_per_invoke
                                and self._press_pagedown(cancellation_token, win_rect=win_rect)
                            ):
                                scroll_steps += 1
                                if self._wait(0.35, cancellation_token):
                                    return abort(
                                        ParasiteFailure.INTERRUPTED,
                                        "Interrupted settling after retry pagedown scroll.",
                                    )
                                assist_calls_used += 1
                                try:
                                    loc = self.local_assist.locate_copy_button(
                                        gemini_hwnd,
                                        win_rect,
                                        self.config.copy_button_names,
                                        exclude_points=list(failed_copy_points),
                                    )
                                except TypeError:
                                    loc = self.local_assist.locate_copy_button(
                                        gemini_hwnd, win_rect, self.config.copy_button_names
                                    )
                            if loc is not None:
                                lx, ly, copy_tier = loc
                                rl, rt, rr, rb = win_rect
                                far_from_excl = all(
                                    math.hypot(lx - ex[0], ly - ex[1]) >= 16.0
                                    for ex in failed_copy_points
                                )
                                if rl <= lx < rr and rt <= ly < rb and far_from_excl:
                                    copy_center = (lx, ly)
                                    rescued_by = rescued_by or f"copy:{copy_tier}"
                        continue

                def _click_copy(target_pt: Tuple[int, int] = active_copy_pt) -> bool:
                    btn = (
                        self.window_backend.find_uia_button(
                            gemini_hwnd, self.config.copy_button_names, pick_last=True
                        )
                        or target_pt
                    )
                    if last_send_pos is not None and math.hypot(
                        btn[0] - last_send_pos[0], btn[1] - last_send_pos[1]
                    ) < 40.0:
                        btn = target_pt
                    return bool(
                        self.mouse.click(
                            x=btn[0],
                            y=btn[1],
                            button="left",
                            clicks=1,
                            cancellation_token=cancellation_token,
                        )
                    )

                attempt_timeout = (
                    min(2.0, self.config.harvest_timeout_sec)
                    if (
                        self.config.local_assist_enabled
                        and self.local_assist is not None
                        and assist_calls_used < self.config.max_local_assist_calls_per_invoke
                    )
                    else self.config.harvest_timeout_sec
                )
                harvested = verifier.execute_harvest(
                    trigger_copy_action=_click_copy,
                    timeout_s=attempt_timeout,
                    cancellation_token=cancellation_token,
                    retrigger_interval_s=1.0,
                )
                if self._is_interrupted(cancellation_token):
                    return abort(ParasiteFailure.INTERRUPTED, "Interrupted during sentinel harvest.")
                if harvested and harvested.strip():
                    break

                if active_copy_pt not in failed_copy_points:
                    failed_copy_points.append(active_copy_pt)
                copy_center = None
                if (
                    self.config.local_assist_enabled
                    and self.local_assist is not None
                    and assist_calls_used < self.config.max_local_assist_calls_per_invoke
                ):
                    assist_calls_used += 1
                    try:
                        loc = self.local_assist.locate_copy_button(
                            gemini_hwnd,
                            win_rect,
                            self.config.copy_button_names,
                            exclude_points=list(failed_copy_points),
                        )
                    except TypeError:
                        loc = self.local_assist.locate_copy_button(
                            gemini_hwnd, win_rect, self.config.copy_button_names
                        )
                    if loc is not None:
                        lx, ly, copy_tier = loc
                        rl, rt, rr, rb = win_rect
                        far_from_excl = all(
                            math.hypot(lx - ex[0], ly - ex[1]) >= 16.0
                            for ex in failed_copy_points
                        )
                        if rl <= lx < rr and rt <= ly < rb and far_from_excl:
                            copy_center = (lx, ly)
                            rescued_by = rescued_by or f"copy:{copy_tier}"

            if not harvested or not harvested.strip():
                gemini_snap = None
                try:
                    gemini_snap = self.capturer.capture_rect(rect_wh)
                except Exception:
                    pass
                return abort(
                    ParasiteFailure.HARVEST_TIMEOUT,
                    "Sentinel clipboard verifier received no response text after clicking Copy.",
                    failure_frame=gemini_snap,
                )

            # --- Step 11: Strict Nonce-Bound Protocol Parse ---
            transitions.append("PARSING")
            parsed = parse_response(
                harvested,
                nonce=nonce,
                phase=request.phase,
                max_response_chars=self.config.max_response_chars,
            )
            if isinstance(parsed, ParasiteFailure):
                return abort(
                    parsed,
                    f"Protocol parser rejected harvested output with {parsed.value}.",
                    harvested_preview=harvested,
                )

            transitions.append("COMPLETED")
            draft_dirty = False
            self._consecutive_breaker_failures = 0
            return ParasiteResult(
                ok=True,
                phase=request.phase,
                plan=parsed.plan,
                action=parsed.action,
                skill_markdown=parsed.skill_markdown,
                parsed_skill=parsed.parsed_skill,
                detail="Symbiosis invocation completed cleanly.",
                duration_sec=max(0.0, self._clock() - start_time),
                identity_mode=identity_mode,
                rescued_by=rescued_by,
                submit_method=submit_method,
                scroll_steps=scroll_steps,
            )

        except Exception as exc:
            logger.exception("Unexpected ParasiteSkill error")
            return abort(
                ParasiteFailure.UNEXPECTED_ERROR,
                f"Unhandled exception: {exc}",
            )
        finally:
            transitions.append("TEARDOWN")
            self._teardown(
                clip_snap=clip_snap,
                gemini_hwnd=gemini_hwnd,
                minimize_gemini=bool(gemini_verified and not suppress_unknown_minimize),
                prior_hwnd=prior_hwnd,
                restore_prior_focus=bool(touched_foreground and prior_hwnd),
                clear_draft=bool(draft_dirty and gemini_verified and identity_mode != "win32_title"),
            )
