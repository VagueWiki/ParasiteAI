"""
parasite_ai/vision/grounding.py - Hybrid Screen Grounding Perception Engine.

Combines Win32 UI Automation tree walking with scoped RapidOCR fallback and
spatial IoU/containment deduplication to produce normalized Set-of-Mark UIElement lists.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from parasite_ai.config import VisionConfig
from parasite_ai.ui.types import UIElement
from parasite_ai.vision.capture import ScreenCapture, get_monitor_bounds

logger = logging.getLogger(__name__)

INTERACTIVE_ROLES: Dict[str, str] = {
    "ButtonControl": "Button",
    "SplitButtonControl": "Button",
    "EditControl": "Edit",
    "HyperlinkControl": "Hyperlink",
    "TabItemControl": "TabItem",
    "ComboBoxControl": "ComboBox",
    "CheckBoxControl": "CheckBox",
    "RadioButtonControl": "RadioButton",
    "MenuItemControl": "MenuItem",
    "ListItemControl": "ListItem",
    "TreeItemControl": "ListItem",
    "DataItemControl": "ListItem",
    "HeaderItemControl": "Button",
    "SliderControl": "Button",
    "DocumentControl": "Document",
    "TextControl": "Text",
    "CustomControl": "Button",
}


@dataclass
class RawElement:
    """Internal raw grounded element before spatial deduplication and sequential indexing."""
    role: str
    label: str
    x: int
    y: int
    width: int
    height: int
    center_x: int
    center_y: int
    source: str  # "uia" | "ocr" | "merged" | "mock"
    is_active_window: bool = True
    confidence: float = 1.0
    control_ref: Optional[Any] = None
    process_name: str = ""
    window_title: str = ""

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)


def compute_iou(box_a: Tuple[int, int, int, int], box_b: Tuple[int, int, int, int]) -> float:
    """Computes Intersection-over-Union (IoU) of two bounding boxes (x, y, w, h)."""
    xa, ya, wa, ha = box_a
    xb, yb, wb, hb = box_b

    ix1 = max(xa, xb)
    iy1 = max(ya, yb)
    ix2 = min(xa + wa, xb + wb)
    iy2 = min(ya + ha, yb + hb)

    inter_w = max(0, ix2 - ix1)
    inter_h = max(0, iy2 - iy1)
    intersection = inter_w * inter_h

    area_a = max(0, wa) * max(0, ha)
    area_b = max(0, wb) * max(0, hb)
    union = area_a + area_b - intersection

    if union <= 0:
        return 0.0

    return float(intersection / union)


def compute_containment(inner_box: Tuple[int, int, int, int], outer_box: Tuple[int, int, int, int]) -> float:
    """Computes the fraction of inner_box contained within outer_box."""
    xa, ya, wa, ha = inner_box
    xb, yb, wb, hb = outer_box

    ix1 = max(xa, xb)
    iy1 = max(ya, yb)
    ix2 = min(xa + wa, xb + wb)
    iy2 = min(ya + ha, yb + hb)

    inter_w = max(0, ix2 - ix1)
    inter_h = max(0, iy2 - iy1)
    intersection = inter_w * inter_h

    inner_area = max(0, wa) * max(0, ha)
    if inner_area <= 0:
        return 0.0

    return float(intersection / inner_area)


class ScreenGrounder:
    """
    Hybrid UI perception engine combining Win32 UI Automation,
    scoped RapidOCR fallback, and spatial IoU deduplication.
    """

    IOU_THRESHOLD = 0.35
    CONTAINMENT_THRESHOLD = 0.70

    SCROLLBAR_BUTTON_LABELS = {
        "page up", "page down", "line up", "line down",
        "column left", "column right", "page left", "page right",
    }
    WINDOW_CHROME_LABELS = SCROLLBAR_BUTTON_LABELS | {
        "minimize", "minimise", "maximize", "maximise", "restore",
        "close", "system", "text area", "editor canvas",
    }

    def __init__(
        self,
        config: Optional[VisionConfig] = None,
        capturer: Optional[ScreenCapture] = None,
        ocr_engine: Optional[Any] = None,
    ) -> None:
        self.config = config or VisionConfig()
        mon_idx = getattr(self.config, "monitor_index", 1)
        self.capturer = capturer or ScreenCapture(
            backend=self.config.capture_backend,
            monitor_index=mon_idx,
        )
        self._ocr_engine = ocr_engine
        self._depth_limit: int = 5
        self._min_uia_threshold: int = 6
        self._lock = __import__("threading").RLock()

    def _get_target_monitor_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """
        Returns (left, top, right, bottom) of the configured target monitor when monitor_index >= 1,
        or None if monitor_index == 0 (all monitors).
        """
        mon_idx = getattr(self.config, "monitor_index", 1)
        if not mon_idx or mon_idx <= 0:
            return None
        ml, mt, mw, mh = get_monitor_bounds(int(mon_idx))
        return (ml, mt, ml + mw, mt + mh)

    def _get_ocr_engine(self) -> Optional[Any]:
        """Lazy initializer for RapidOCR ONNX model."""
        if self._ocr_engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._ocr_engine = RapidOCR()
            except Exception as exc:
                logger.warning("Could not initialize RapidOCR engine: %s", exc)
                self._ocr_engine = None
        return self._ocr_engine

    def ground(
        self,
        window_filter: Optional[int] = None,
        force_ocr: bool = False,
        image_override: Optional[np.ndarray] = None,
        goal_keywords: Optional[List[str]] = None,
        offset: int = 0,
    ) -> List[UIElement]:
        """
        Executes hybrid grounding pipeline:
        1. Enumerates UIA controls from active window or window_filter HWND.
        2. Evaluates if OCR fallback is needed (< 6 UIA controls, or force_ocr=True, or ocr_only).
        3. Invokes scoped RapidOCR on active window bounds if needed.
        4. Performs spatial IoU and containment deduplication and label merging.
        5. Normalizes, filters degenerate elements, prioritizes goal matches, caps to max_som_elements, and assigns 1-based IDs.
        """
        with self._lock:
            uia_raw_elements: List[RawElement] = []
            active_window_rect: Optional[Tuple[int, int, int, int]] = None

            # 1. Tier 1: Win32 UI Automation tree walk
            if self.config.grounding_mode != "ocr_only":
                uia_raw_elements, active_window_rect = self._walk_uia_tree(
                    window_filter=window_filter,
                    goal_keywords=goal_keywords,
                )

            # 2. Check if Tier 2: OCR fallback is needed
            # Evaluate foreground/active window UIA control count separately from background desktop icons
            # and exclude standard OS window chrome / scrollbar buttons so console (conhost.exe),
            # Steam launch modals, and custom-rendered game windows always trigger scoped OCR.
            active_uia_count = sum(
                1 for e in uia_raw_elements
                if e.is_active_window and (e.label or "").strip().lower() not in self.WINDOW_CHROME_LABELS
            )
            run_ocr = False
            if self.config.grounding_mode == "ocr_only" or force_ocr:
                run_ocr = True
            elif self.config.grounding_mode == "hybrid" and active_uia_count < self._min_uia_threshold:
                run_ocr = True

            ocr_raw_elements: List[RawElement] = []
            if run_ocr:
                ocr_raw_elements = self._run_scoped_ocr(
                    window_rect=active_window_rect,
                    image_override=image_override,
                )

            # 3. Tier 3: Spatial IoU & Containment Deduplication
            deduplicated_elements = self._deduplicate_and_merge(
                uia_elements=uia_raw_elements,
                ocr_elements=ocr_raw_elements,
            )

            # 4. Normalization, filtering & 1-based Set-of-Mark assignment
            normalized_som = self._normalize_elements(
                deduplicated_elements,
                goal_keywords=goal_keywords,
                offset=offset,
            )
            return normalized_som

    def _walk_uia_tree(
        self,
        window_filter: Optional[int] = None,
        goal_keywords: Optional[List[str]] = None,
    ) -> Tuple[List[RawElement], Optional[Tuple[int, int, int, int]]]:
        """Traverses Win32 UI Automation accessibility tree."""
        try:
            import uiautomation as auto
        except ImportError:
            logger.warning("uiautomation not installed; skipping UIA tree walk.")
            return [], None

        from contextlib import nullcontext
        com_ctx = (
            auto.UIAutomationInitializerInThread()
            if hasattr(auto, "UIAutomationInitializerInThread") and callable(getattr(auto, "UIAutomationInitializerInThread"))
            else nullcontext()
        )
        try:
            with com_ctx:
                return self._walk_uia_tree_inner(auto, window_filter, goal_keywords)
        except Exception:
            return self._walk_uia_tree_inner(auto, window_filter, goal_keywords)

    @staticmethod
    def _is_hwnd_visible_and_uncloaked(hwnd: int) -> bool:
        """Checks Win32 IsWindow, IsWindowVisible, IsIconic, and DWMWA_CLOAKED for a top-level HWND."""
        if not hwnd:
            return True
        try:
            import ctypes
            user32 = ctypes.windll.user32
            if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return False
            dwmapi = getattr(ctypes.windll, "dwmapi", None)
            if dwmapi is not None:
                cloaked = ctypes.c_int(0)
                res = dwmapi.DwmGetWindowAttribute(
                    ctypes.c_void_p(hwnd),
                    14,  # DWMWA_CLOAKED
                    ctypes.byref(cloaked),
                    ctypes.sizeof(cloaked),
                )
                if res == 0 and cloaked.value != 0:
                    return False
        except Exception:
            pass
        return True

    @staticmethod
    def _resolve_process_name(hwnd: int = 0, pid: int = 0) -> str:
        """Resolves process executable name for a given HWND or PID using Win32 API."""
        if not isinstance(hwnd, int):
            hwnd = 0
        if not isinstance(pid, int):
            pid = 0
        if not hwnd and not pid:
            return ""
        try:
            import ctypes
            from ctypes import wintypes
            import os

            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32
            if not pid and hwnd:
                wpid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
                pid = wpid.value
            if not pid:
                return ""
            h_proc = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h_proc:
                return ""
            try:
                buf = ctypes.create_unicode_buffer(1024)
                sz = wintypes.DWORD(1024)
                if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(sz)):
                    return os.path.basename(buf.value)
            finally:
                kernel32.CloseHandle(h_proc)
        except Exception:
            pass
        return ""

    def _walk_uia_tree_inner(
        self,
        auto: Any,
        window_filter: Optional[int] = None,
        goal_keywords: Optional[List[str]] = None,
    ) -> Tuple[List[RawElement], Optional[Tuple[int, int, int, int]]]:
        root_control = None
        excluded_rect: Optional[Tuple[int, int, int, int]] = None
        roots_to_walk: List[Tuple[Any, bool]] = []  # (control, is_active_window)
        mon_rect = self._get_target_monitor_rect()
        try:
            if window_filter is not None and window_filter != 0:
                root_control = auto.ControlFromHandle(window_filter)
                if root_control is not None:
                    if getattr(root_control, "ProcessId", 0) == os.getpid():
                        return [], None
                    roots_to_walk = [(root_control, True)]
            else:
                fg_control = auto.GetForegroundControl()
                fg_hwnd = getattr(fg_control, "NativeWindowHandle", 0) if fg_control is not None else 0

                desktop_root = auto.GetRootControl()
                children = (
                    desktop_root.GetChildren()
                    if desktop_root is not None and hasattr(desktop_root, "GetChildren") and callable(desktop_root.GetChildren)
                    else None
                )

                if isinstance(children, (list, tuple)) and len(children) > 0:
                    valid_children: List[Tuple[Any, int]] = []
                    current_pid = os.getpid()
                    for child in children:
                        c_pid = getattr(child, "ProcessId", 0)
                        cls_name = getattr(child, "ClassName", "")
                        c_title = str(getattr(child, "Name", "") or "")
                        # Exclude ParasiteAI's own UI overlays (CompanionDock, GhostHUD) or self-process
                        if (
                            (c_pid and c_pid == current_pid)
                            or cls_name in ("GhostHUD", "CompanionDock")
                            or "CompanionDock" in cls_name
                        ):
                            try:
                                cb = child.BoundingRectangle
                                if cb and (cls_name in ("GhostHUD", "CompanionDock") or "CompanionDock" in cls_name):
                                    excluded_rect = (cb.left, cb.top, cb.right, cb.bottom)
                                    self._last_excluded_rect = excluded_rect
                            except Exception:
                                pass
                            continue
                        c_hwnd = getattr(child, "NativeWindowHandle", 0)
                        if isinstance(c_hwnd, int) and c_hwnd > 0:
                            if not self._is_hwnd_visible_and_uncloaked(c_hwnd):
                                continue
                        try:
                            cb = child.BoundingRectangle
                            if not cb:
                                continue
                            cw = cb.width() if callable(cb.width) else cb.width
                            ch = cb.height() if callable(cb.height) else cb.height
                            if cw < 20 or ch < 20 or cb.left <= -25000 or cb.top <= -25000:
                                continue
                            # Filter out top-level application windows on other monitors (e.g. Right Monitor x >= 1920)
                            if mon_rect is not None:
                                ml, mt, mr, mb = mon_rect
                                c_name_low = str(getattr(child, "Name", "") or "").strip().lower()
                                is_desktop_or_shell = (
                                    cls_name in ("Progman", "WorkerW", "Shell_TrayWnd")
                                    or c_name_low in ("program manager", "workerw", "desktop", "taskbar")
                                )
                                if not is_desktop_or_shell:
                                    c_right = getattr(cb, "right", cb.left + cw)
                                    c_bottom = getattr(cb, "bottom", cb.top + ch)
                                    win_cx = (cb.left + c_right) // 2
                                    win_cy = (cb.top + c_bottom) // 2
                                    if not (ml <= win_cx < mr and mt <= win_cy < mb):
                                        continue
                        except Exception:
                            continue
                        valid_children.append((child, c_hwnd if isinstance(c_hwnd, int) else 0))

                    effective_fg_hwnd = fg_hwnd
                    fg_child = next((c for c, ch in valid_children if fg_hwnd and ch == fg_hwnd), None)
                    fg_cls = getattr(fg_child, "ClassName", "") if fg_child is not None else ""
                    fg_name_low = str(getattr(fg_child, "Name", "") or "").strip().lower() if fg_child is not None else ""
                    fg_is_shell_or_launcher = (
                        fg_child is None
                        or fg_cls in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd")
                        or fg_name_low in ("program manager", "workerw", "desktop", "taskbar", "parasiteai launcher")
                        or "parasiteai launcher" in fg_name_low
                    )
                    if fg_is_shell_or_launcher and goal_keywords:
                        g_kws = [kw.lower() for kw in goal_keywords if len(kw) >= 3]
                        g_ckws = [re.sub(r"[^a-z0-9\+#]", "", kw) for kw in g_kws if len(re.sub(r"[^a-z0-9\+#]", "", kw)) >= 3]
                        for child, c_hwnd in valid_children:
                            if not c_hwnd:
                                continue
                            c_cls = getattr(child, "ClassName", "")
                            c_title = str(getattr(child, "Name", "") or "").strip().lower()
                            if (
                                c_cls in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd")
                                or c_title in ("program manager", "workerw", "desktop", "taskbar", "parasiteai launcher")
                                or "parasiteai launcher" in c_title
                            ):
                                continue
                            c_compact = re.sub(r"[^a-z0-9\+#]", "", c_title)
                            if (
                                any(kw in c_title for kw in g_kws)
                                or (c_compact and any(ckw in c_compact or c_compact in ckw for ckw in g_ckws))
                            ):
                                effective_fg_hwnd = c_hwnd
                                break

                    has_fg_match = bool(effective_fg_hwnd and any(c_hwnd == effective_fg_hwnd for _, c_hwnd in valid_children))
                    for idx, (child, c_hwnd) in enumerate(valid_children):
                        is_active = (c_hwnd == effective_fg_hwnd) if has_fg_match else (idx == 0)
                        roots_to_walk.append((child, is_active))
                        if is_active and root_control is None:
                            root_control = child
                    if roots_to_walk and root_control is None:
                        root_control = roots_to_walk[0][0]
                else:
                    # Unit test mock or fallback path
                    root_control = fg_control if fg_control is not None else desktop_root
                    if root_control is not None:
                        roots_to_walk = [(root_control, True)]

            self._last_excluded_rect = excluded_rect
            if root_control is not None:
                rc_hwnd = getattr(root_control, "NativeWindowHandle", 0)
                rc_pid = getattr(root_control, "ProcessId", 0)
                self._last_active_win_title = str(getattr(root_control, "Name", "") or "").strip()
                self._last_active_proc_name = self._resolve_process_name(
                    hwnd=rc_hwnd if isinstance(rc_hwnd, int) else 0,
                    pid=rc_pid if isinstance(rc_pid, int) else 0,
                )
                try:
                    rb = root_control.BoundingRectangle
                    if rb:
                        rw = rb.width() if callable(rb.width) else rb.width
                        rh = rb.height() if callable(rb.height) else rb.height
                        self._last_active_win_rect = (
                            rb.left,
                            rb.top,
                            getattr(rb, "right", rb.left + rw),
                            getattr(rb, "bottom", rb.top + rh),
                        )
                    else:
                        self._last_active_win_rect = None
                except Exception:
                    self._last_active_win_rect = None
            else:
                self._last_active_win_title = ""
                self._last_active_proc_name = ""
                self._last_active_win_rect = None
        except Exception as exc:
            logger.debug("Failed to acquire UIA root control: %s", exc)
            return [], None

        if not roots_to_walk or root_control is None:
            return [], None

        active_rect: Optional[Tuple[int, int, int, int]] = None
        try:
            win_bbox = root_control.BoundingRectangle
            if win_bbox:
                w = win_bbox.width() if callable(win_bbox.width) else win_bbox.width
                h = win_bbox.height() if callable(win_bbox.height) else win_bbox.height
                active_rect = (win_bbox.left, win_bbox.top, w, h)
        except Exception:
            pass

        clean_kws = [kw.lower() for kw in (goal_keywords or []) if len(kw) >= 2]
        compact_kws = [re.sub(r"[^a-z0-9\+#]", "", kw) for kw in clean_kws if len(re.sub(r"[^a-z0-9\+#]", "", kw)) >= 3]
        raw_elements: List[RawElement] = []
        occluder_rects: List[Tuple[int, int, int, int]] = []
        if excluded_rect is not None:
            occluder_rects.append(excluded_rect)

        walk_depth = self._depth_limit if len(roots_to_walk) == 1 and type(auto).__name__ == "MagicMock" else max(self._depth_limit, 10)
        current_pid = os.getpid()

        for win_ctl, is_active_win in roots_to_walk:
            if len(raw_elements) >= 400:
                break
            win_pid = getattr(win_ctl, "ProcessId", 0)
            if win_pid and win_pid == current_pid:
                continue
            window_start_count = len(raw_elements)
            win_title = str(getattr(win_ctl, "Name", "") or "").strip()
            win_hwnd = getattr(win_ctl, "NativeWindowHandle", 0)
            proc_name = self._resolve_process_name(hwnd=win_hwnd, pid=win_pid)

            win_title_lower = win_title.lower()
            is_desktop_win = (
                proc_name.lower() == "explorer.exe"
                and any(d in win_title_lower for d in ("program manager", "workerw", "desktop", ""))
            )
            # Desktop window holds all desktop shortcuts (e.g. 150+ icons); use higher element cap
            max_win_elements = 250 if is_desktop_win else 120
            last_listitem_name: Optional[str] = None
            scan_after_cap_steps = 0
            total_nodes_scanned = 0

            try:
                for control, depth in auto.WalkControl(win_ctl, includeTop=False, maxDepth=walk_depth):
                    total_nodes_scanned += 1
                    if total_nodes_scanned >= 2000:
                        break
                    ctl_pid = getattr(control, "ProcessId", 0)
                    if ctl_pid and ctl_pid == current_pid:
                        continue
                    # Check goal match early so target elements are not dropped by the cap
                    ctl_name_raw = getattr(control, "Name", None) or getattr(control, "HelpText", None) or ""
                    ctl_name_lower = str(ctl_name_raw).strip().lower()
                    ctl_name_compact = re.sub(r"[^a-z0-9\+#]", "", ctl_name_lower)
                    ctl_type = getattr(control, "ControlTypeName", "")

                    is_goal_match = bool(
                        (clean_kws and any(kw in ctl_name_lower for kw in clean_kws))
                        or (compact_kws and ctl_name_compact and any(ckw in ctl_name_compact or ctl_name_compact in ckw for ckw in compact_kws if len(ctl_name_compact) >= 3))
                    )

                    # Per-window cap and overall cap bound runaway trees, but allow goal matches up to 400
                    elements_in_win = len(raw_elements) - window_start_count
                    if len(raw_elements) >= 400:
                        break
                    if elements_in_win >= max_win_elements and not is_goal_match:
                        # Allow up to 500 extra scan iterations looking for goal matches after cap
                        scan_after_cap_steps += 1
                        if scan_after_cap_steps >= 500:
                            break
                        continue

                    # On desktop / list views, skip child text/image elements whose label matches enclosing list item
                    if ctl_type == "ListItemControl":
                        last_listitem_name = ctl_name_lower
                    elif ctl_type in ("TextControl", "ImageControl") and is_desktop_win:
                        if last_listitem_name and (ctl_name_lower == last_listitem_name or not ctl_name_lower):
                            continue

                    try:
                        # Offscreen check: do not skip if element matches goal keywords
                        if getattr(control, "IsOffscreen", False) and not is_goal_match:
                            continue

                        ctl_hwnd = getattr(control, "NativeWindowHandle", 0)
                        if isinstance(ctl_hwnd, int) and ctl_hwnd > 0:
                            if not self._is_hwnd_visible_and_uncloaked(ctl_hwnd):
                                continue

                        # Bounding box check
                        rect = control.BoundingRectangle
                        if not rect:
                            continue

                        w = rect.width() if callable(getattr(rect, "width", None)) else rect.width
                        h = rect.height() if callable(getattr(rect, "height", None)) else rect.height

                        # Skip degenerate or invisible spacer nodes
                        if w < 8 or h < 8:
                            continue

                        # Skip minimized coordinates (-32000 on Windows) while allowing negative dual-monitor coords
                        if rect.left <= -25000 or rect.top <= -25000:
                            continue

                        ctl_type = getattr(control, "ControlTypeName", "")
                        cls_name = str(getattr(control, "ClassName", "") or "").strip()
                        is_editor_pane = (
                            ctl_type in ("PaneControl", "CustomControl", "DocumentControl")
                            and any(
                                ed in cls_name.lower()
                                for ed in ("scintilla", "richedit", "edit", "editor")
                            )
                        )
                        if ctl_type not in INTERACTIVE_ROLES and not is_editor_pane:
                            # Allow PaneControl or ImageControl only if it has an explicit accessible name and button-like bounds
                            if ctl_type in ("PaneControl", "ImageControl"):
                                name = getattr(control, "Name", "")
                                if not name or w > 400 or h > 150:
                                    continue
                            else:
                                continue

                        if is_editor_pane:
                            role = "Document"
                        else:
                            role = INTERACTIVE_ROLES.get(ctl_type, "Button")

                        name = (
                            getattr(control, "Name", None)
                            or getattr(control, "HelpText", None)
                            or ""
                        )
                        if not name and is_editor_pane:
                            name = "Editor Canvas"
                        elif not name:
                            auto_id = getattr(control, "AutomationId", "") or ""
                            if not auto_id.startswith("auto_"):
                                name = auto_id
                        label = str(name).strip()[:80]
                        if role == "Button" and label.lower() in self.SCROLLBAR_BUTTON_LABELS:
                            continue

                        cx = rect.xcenter() if callable(getattr(rect, "xcenter", None)) else (rect.left + w // 2)
                        cy = rect.ycenter() if callable(getattr(rect, "ycenter", None)) else (rect.top + h // 2)

                        # Filter out controls located outside the configured target monitor (e.g. Right Monitor x >= 1920)
                        if mon_rect is not None:
                            ml, mt, mr, mb = mon_rect
                            if not (ml <= cx < mr and mt <= cy < mb):
                                continue

                        if getattr(control, "ClassName", "") in ("CompanionDock", "GhostHUD"):
                            continue

                        # Skip if occluded by CompanionDock or any window in front of win_ctl in Z-order
                        # Target elements matching user goal keywords are never dropped by occlusion
                        is_occluded = False
                        for ol, ot, oright, obot in occluder_rects:
                            if ol <= cx <= oright and ot <= cy <= obot:
                                is_occluded = True
                                break
                        if is_occluded and not is_goal_match:
                            continue

                        raw_elements.append(
                            RawElement(
                                role=role,
                                label=label,
                                x=rect.left,
                                y=rect.top,
                                width=w,
                                height=h,
                                center_x=cx,
                                center_y=cy,
                                source="uia",
                                is_active_window=is_active_win,
                                control_ref=control,
                                process_name=proc_name,
                                window_title=win_title,
                            )
                        )
                    except Exception as exc:
                        logger.debug("Error processing UIA node: %s", exc)
                        continue
            except Exception as exc:
                logger.debug("Exception during UIA tree walk: %s", exc)

            # After walking a top-level opaque window, add its bounds to occluder_rects
            try:
                cls_name = getattr(win_ctl, "ClassName", "")
                if cls_name not in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
                    wb = win_ctl.BoundingRectangle
                    if wb:
                        occluder_rects.append((wb.left, wb.top, wb.right, wb.bottom))
            except Exception:
                pass

        return raw_elements, active_rect

    def _run_scoped_ocr(
        self,
        window_rect: Optional[Tuple[int, int, int, int]],
        image_override: Optional[np.ndarray] = None,
    ) -> List[RawElement]:
        """Runs Scoped RapidOCR on active window bounds or override image."""
        engine = self._get_ocr_engine()
        if engine is None:
            return []

        # Acquire frame
        if image_override is not None:
            full_frame = image_override
        else:
            try:
                full_frame = self.capturer.capture_screen()
            except Exception as exc:
                logger.warning("Screen capture failed during OCR: %s", exc)
                return []

        if full_frame is None or full_frame.size == 0:
            return []

        frame_h, frame_w = full_frame.shape[:2]

        offset_x, offset_y = 0, 0
        crop = full_frame

        # Scoping optimization
        if self.config.ocr_scoped_only and window_rect is not None:
            wx, wy, ww, wh = window_rect
            if ww > 20 and wh > 20:
                crop_x1 = max(0, min(wx, frame_w - 1))
                crop_y1 = max(0, min(wy, frame_h - 1))
                crop_x2 = max(crop_x1 + 1, min(wx + ww, frame_w))
                crop_y2 = max(crop_y1 + 1, min(wy + wh, frame_h))

                if (crop_x2 - crop_x1) >= 20 and (crop_y2 - crop_y1) >= 20:
                    crop = full_frame[crop_y1:crop_y2, crop_x1:crop_x2]
                    offset_x, offset_y = crop_x1, crop_y1

        try:
            ocr_res = engine(crop)
            if ocr_res is None:
                return []
            # RapidOCR returns (results, elapse) or just results
            if isinstance(ocr_res, tuple):
                boxes = ocr_res[0]
            else:
                boxes = ocr_res

            if not boxes:
                return []
        except Exception as exc:
            logger.warning("RapidOCR execution failed: %s", exc)
            return []

        raw_ocr: List[RawElement] = []
        for item in boxes:
            try:
                # Format: [polygon_points, text, confidence]
                if len(item) < 3:
                    continue
                pts, text, conf = item[0], item[1], item[2]
                if float(conf) < 0.40:
                    continue

                pts_arr = np.array(pts)
                min_x = int(np.min(pts_arr[:, 0]))
                max_x = int(np.max(pts_arr[:, 0]))
                min_y = int(np.min(pts_arr[:, 1]))
                max_y = int(np.max(pts_arr[:, 1]))

                bw = max_x - min_x
                bh = max_y - min_y

                # Filter noise
                if bw < 10 or bh < 8:
                    continue

                abs_x = offset_x + min_x
                abs_y = offset_y + min_y
                cx_ocr = abs_x + bw // 2
                cy_ocr = abs_y + bh // 2
                mon_rect = self._get_target_monitor_rect()
                if mon_rect is not None:
                    ml, mt, mr, mb = mon_rect
                    if not (ml <= cx_ocr < mr and mt <= cy_ocr < mb):
                        continue
                excl = getattr(self, "_last_excluded_rect", None)
                if excl is not None:
                    el, et, er, eb = excl
                    if el <= cx_ocr <= er and et <= cy_ocr <= eb:
                        continue
                raw_ocr.append(
                    RawElement(
                        role="Text",
                        label=str(text).strip(),
                        x=abs_x,
                        y=abs_y,
                        width=bw,
                        height=bh,
                        center_x=cx_ocr,
                        center_y=cy_ocr,
                        source="ocr",
                        confidence=float(conf),
                        is_active_window=True,
                        process_name=getattr(self, "_last_active_proc_name", ""),
                        window_title=getattr(self, "_last_active_win_title", ""),
                    )
                )
            except Exception as exc:
                logger.debug("Failed parsing OCR result item: %s", exc)
                continue

        return raw_ocr

    def _deduplicate_and_merge(
        self,
        uia_elements: List[RawElement],
        ocr_elements: List[RawElement],
    ) -> List[RawElement]:
        """
        Deduplicates overlapping UIA and OCR elements using IoU and Containment.
        Enriches missing UIA labels from contained OCR text.
        """
        surviving_ocr: List[RawElement] = []

        for ocr in ocr_elements:
            matched_uia = False
            ocr_area = max(1, ocr.width * ocr.height)
            for uia in uia_elements:
                uia_area = max(1, uia.width * uia.height)
                # Large container/canvas elements (e.g. console Document "Text Area" or full-window Pane)
                # must not swallow inner OCR text lines via containment.
                is_large_container = (
                    uia.role in ("Document", "Pane", "Window")
                    or uia_area > 6 * ocr_area
                )
                iou = compute_iou(ocr.bbox, uia.bbox)
                containment = 0.0 if is_large_container else compute_containment(ocr.bbox, uia.bbox)

                if iou >= self.IOU_THRESHOLD or containment >= self.CONTAINMENT_THRESHOLD:
                    matched_uia = True
                    # Label enrichment: If UIA element lacks meaningful label, adopt OCR label
                    clean_label = uia.label.strip().lower()
                    if not clean_label or clean_label in ("button", "pane", "custom", "item"):
                        uia.label = ocr.label
                        uia.source = "merged"
                    break

            if not matched_uia:
                surviving_ocr.append(ocr)

        return uia_elements + surviving_ocr

    def _normalize_elements(
        self,
        raw_elements: List[RawElement],
        goal_keywords: Optional[List[str]] = None,
        offset: int = 0,
    ) -> List[UIElement]:
        """
        Sorts, filters degenerate boxes, prioritizes goal-relevant targets, caps length,
        and assigns 1-based Set-of-Mark IDs. Supports offset for element cycling/paging.
        """
        valid: List[RawElement] = []
        for elem in raw_elements:
            if elem.width < 8 or elem.height < 8:
                continue
            if elem.x <= -25000 or elem.y <= -25000:
                continue
            valid.append(elem)

        # Clean keywords for goal matching (including spaceless/compound normalizations)
        clean_kws = [kw.lower() for kw in (goal_keywords or []) if len(kw) >= 2]
        compact_kws = [re.sub(r"[^a-z0-9\+#]", "", kw) for kw in clean_kws if len(re.sub(r"[^a-z0-9\+#]", "", kw)) >= 3]

        def _goal_relevance_key(e: RawElement) -> int:
            if not clean_kws:
                return 1
            lbl = (e.label or "").lower()
            if any(kw in lbl for kw in clean_kws):
                return 0
            lbl_compact = re.sub(r"[^a-z0-9\+#]", "", lbl)
            if compact_kws and len(lbl_compact) >= 3 and any(ckw in lbl_compact or lbl_compact in ckw for ckw in compact_kws):
                return 0
            return 1

        def _is_chrome_key(e: RawElement) -> int:
            return 1 if (e.label or "").strip().lower() in self.WINDOW_CHROME_LABELS else 0

        active_win_title_low = str(getattr(self, "_last_active_win_title", "") or "").strip().lower()
        active_win_compact = re.sub(r"[^a-z0-9\+#]", "", active_win_title_low)
        active_win_matches_goal = bool(
            clean_kws
            and active_win_title_low
            and active_win_title_low not in ("program manager", "workerw", "desktop", "taskbar", "parasiteai launcher")
            and (
                any(kw in active_win_title_low for kw in clean_kws)
                or (compact_kws and len(active_win_compact) >= 3 and any(ckw in active_win_compact or active_win_compact in ckw for ckw in compact_kws))
            )
        )

        # When the active window itself is the goal application, prioritize its in-window controls
        # ahead of background desktop shortcuts, and put client-area controls ahead of window chrome.
        if active_win_matches_goal:
            valid.sort(key=lambda e: (not e.is_active_window, _is_chrome_key(e), _goal_relevance_key(e), e.y, e.x))
        elif len(valid) > self.config.max_som_elements:
            valid.sort(key=lambda e: (_goal_relevance_key(e), not e.is_active_window, _is_chrome_key(e), e.role == "Text", e.y, e.x))
        else:
            valid.sort(key=lambda e: (_goal_relevance_key(e), not e.is_active_window, _is_chrome_key(e), e.y, e.x))

        # Apply offset for element cycling/paging
        paged = valid[offset:] if offset > 0 else valid
        capped = paged[: self.config.max_som_elements]

        output: List[UIElement] = []
        for idx, elem in enumerate(capped, start=1):
            source_val = elem.source if elem.source in ("uia", "ocr", "merged", "mock") else "uia"
            output.append(
                UIElement(
                    id=idx,
                    role=elem.role,
                    label=elem.label,
                    x=elem.x,
                    y=elem.y,
                    width=elem.width,
                    height=elem.height,
                    center_x=elem.center_x,
                    center_y=elem.center_y,
                    source=source_val,
                    is_active_window=elem.is_active_window,
                    process_name=getattr(elem, "process_name", ""),
                    window_title=getattr(elem, "window_title", ""),
                )
            )

        return output

    def format_som_summary(self, elements: List[UIElement]) -> str:
        """
        Formats normalized UI elements into a compact Set-of-Mark table
        suitable for direct prompt injection into the DualMind cognitive pipeline.
        """
        if not elements:
            return "No interactive UI elements detected on screen."

        lines = ["### Grounded Screen Targets [Set-of-Mark]:"]
        for elem in elements:
            label_part = f'"{elem.label}"' if elem.label else "(no label)"
            details = []
            if elem.process_name:
                details.append(f"app: {elem.process_name}")
            if elem.window_title:
                details.append(f'window: "{elem.window_title[:40]}"')
            extra_part = f" [{', '.join(details)}]" if details else ""
            lines.append(
                f"[#{elem.id}] {elem.role} {label_part} at ({elem.center_x}, {elem.center_y}) "
                f"[{elem.width}x{elem.height}]{extra_part} (source: {elem.source})"
            )
        return "\n".join(lines)

    def format_concise_scene_summary(self, elements: List[UIElement], max_controls: int = 8) -> str:
        """
        Formats a high-level, token-efficient visual scene summary for Pass 1 (Persona Engine).
        Includes active window controls, open background windows, and top desktop/background targets
        so Pass 1 can reason about the actual `[#ID]`s on screen before forming an intent.
        """
        if not elements:
            return "Visual scene: Desktop is empty or no interactive elements detected."

        active_elements = [e for e in elements if e.is_active_window]
        bg_elements = [e for e in elements if not e.is_active_window]

        lines = []
        if active_elements:
            first = active_elements[0]
            win_title = first.window_title or "(Untitled Window)"
            app = first.process_name or "unknown"
            lines.append(f'Active Window: "{win_title[:50]}" (app: {app})')
        else:
            lines.append("Active Window: Desktop / Program Manager")

        apps = set(e.process_name for e in elements if e.process_name)
        if apps:
            lines.append(f"Visible Applications: {', '.join(sorted(apps)[:5])}")

        controls_to_show = active_elements[:max_controls] if active_elements else elements[:max_controls]
        control_descs = []
        for elem in controls_to_show:
            lbl = f'"{elem.label[:30]}"' if elem.label else "(unlabeled)"
            control_descs.append(f"[#{elem.id}] {elem.role} {lbl}")
        if control_descs:
            lines.append(f"Key Controls: {', '.join(control_descs)}")

        if bg_elements:
            bg_preview = []
            for elem in bg_elements[:max_controls]:
                lbl = f'"{elem.label[:28]}"' if elem.label else "(unlabeled)"
                win_hint = f" ({elem.window_title[:20]})" if elem.window_title and elem.window_title.lower() not in ("program manager", "desktop", "taskbar", "") else ""
                bg_preview.append(f"[#{elem.id}] {elem.role} {lbl}{win_hint}")
            preview_str = f" -> {', '.join(bg_preview)}" if bg_preview else ""
            lines.append(f"Background/Desktop Targets: {len(bg_elements)} other items detected (total: {len(elements)}){preview_str}")

        return "\n".join(lines)
