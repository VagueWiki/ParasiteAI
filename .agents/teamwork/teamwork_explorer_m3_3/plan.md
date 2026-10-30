# Milestone M3 Technical Implementation Plan: UI Integration, Thread Bridges & Test Architecture

**Author**: `teamwork_explorer_m3_3`  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_3\`  
**Milestone**: M3 — Desktop Companion Dock & Ghost-Hand Overlay  
**Scope**: UI Subsystem Integration, Cross-Thread Signal Bridges, Package Exports (`parasite_ai/ui/`), High-DPI Awareness, Headless CI Compatibility, and Full Test Suite Architecture (`tests/test_companion_dock.py`, `tests/test_ghost_hud.py`).

---

## 1. Executive Summary & Integration Architecture

Milestone M3 delivers ParasiteAI's user-facing visual and targeting presence on the physical Windows desktop:
1. **Desktop Companion Dock (`parasite_ai/ui/companion_dock.py`)**: Always-on-top frameless window displaying character avatar, internal thoughts, dialogue speech bubbles, live telemetry, perception preview, goal input, and pause/panic controls.
2. **Ghost-Hand Screen Overlay HUD (`parasite_ai/ui/ghost_hud.py`)**: Transparent, click-through Win32 layered overlay rendering numbered Set-of-Mark (SoM) bounding boxes `[#1..#N]` and a 300ms pre-click reticle with Bézier trajectory path preview.

Because ParasiteAI executes its cognitive loop, screen grounding, and physical mouse/keyboard drivers in **background worker threads**, direct manipulation of Qt GUI widgets from background threads is forbidden and will cause instant Qt crashes, memory corruption, or GDI deadlocks.

This document provides the definitive integration specification for:
- **`parasite_ai/ui/bridge.py`**: A thread-safe `UIBridge(QObject)` using Qt's `QueuedConnection` mechanism for seamless cross-thread communication.
- **`parasite_ai/ui/types.py`**: Strongly typed data contracts for `UIElement` / `TargetElement`, states, moods, and visual color palettes.
- **`parasite_ai/ui/dpi.py`**: An idempotent Windows Per-Monitor High-DPI bootstrap (`SetProcessDpiAwareness(2)` / `SetProcessDpiAwarenessContext(-4)`).
- **`parasite_ai/ui/win32_styles.py`**: Safe Win32 extended window styling with headless/offscreen detection.
- **`parasite_ai/ui/__init__.py`**: Clean, unified package exports.
- **`tests/test_companion_dock.py` & `tests/test_ghost_hud.py`**: Complete automated test suites verified under headless CI with `pytest-qt` (`qtbot`) and `QT_QPA_PLATFORM=offscreen`.

```
========================================================================================
                                ARCHITECTURAL DATA FLOW
========================================================================================

    [ Background Worker Threads ]                      [ Main Qt GUI Thread ]
  (Engine, MouseDriver, Offloader)                     (QApplication Event Loop)
                 │                                                 │
                 │ 1. emit(args)                                   │
                 ▼                                                 ▼
      ┌─────────────────────┐       QueuedConnection     ┌─────────────────────┐
      │       UIBridge      │ ─────────────────────────> │    CompanionDock    │
      │   (pyqtSignal hub)  │  (QMetaCallEvent in queue) │  - State & Mood     │
      └─────────────────────┘                            │  - Speech & Thought │
                 │                                       │  - Perception mini  │
                 │ 2. emit(args)                         └─────────────────────┘
                 ▼                                                 │
      ┌─────────────────────┐       QueuedConnection     ┌─────────────────────┐
      │   reticle_callback  │ ─────────────────────────> │      GhostHUD       │
      │  (x, y, 300ms, id)  │                            │  - Click-through    │
      └─────────────────────┘                            │  - SoM [#1..#N]     │
                 ▲                                       │  - 300ms Reticle    │
                 │                                       └─────────────────────┘
                 │ 3. User Goal / Pause / Panic                    │
                 └────────────────── signals ──────────────────────┘
```

---

## 2. Cross-Thread Communication Bridge (`parasite_ai/ui/bridge.py`)

### 2.1 The Cross-Thread Problem in Qt
1. Qt widgets are not thread-safe. Calling any method on `QWidget` (e.g. `setText`, `update`, `show`, `hide`) from a thread other than the thread where `QApplication` was created violates Qt's single-GUI-thread rule.
2. In `MouseDriver.click()` (in `parasite_ai/hands/mouse.py`), a 300ms reticle preview is triggered via `reticle_callback(x, y, duration_ms)`. `MouseDriver` runs on a background worker thread.
3. If `reticle_callback` directly called `hud.show_reticle(x, y, 300)`, Qt would attempt to start a `QTimer` from the wrong thread, triggering:
   `QObject::startTimer: Timers can only be used with threads started with QThread` or an access violation crash.

### 2.2 Solution: `UIBridge` with `Qt.ConnectionType.QueuedConnection`
In PyQt6, emitting a `pyqtSignal` is thread-safe and can be invoked from any standard Python `threading.Thread` or `QThread`. When connected with `Qt.ConnectionType.QueuedConnection` (or `AutoConnection` across different threads), Qt packages the signal arguments into an event and posts it to the main thread's event loop via `QCoreApplication.postEvent()`. The slot then executes safely on the main GUI thread.

### 2.3 Specification: `UIBridge` Implementation

```python
"""
parasite_ai/ui/bridge.py - Cross-Thread UI Communication Bridge.
Provides a centralized, thread-safe signal hub connecting background worker threads
with the CompanionDock and GhostHUD widgets on the Qt main GUI thread.
"""

from __future__ import annotations

import logging
import queue
from typing import Any, Callable, List, Optional, Tuple
from PyQt6.QtCore import QObject, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap

from parasite_ai.ui.types import UIElement


logger = logging.getLogger(__name__)


class UIBridge(QObject):
    """
    Central thread-safe signal bridge for ParasiteAI.
    Background threads call the public notify_* methods;
    Qt widgets on the main thread connect to the corresponding pyqtSignals.
    """

    # --- Background Worker -> GUI Signals ---
    sig_state_changed = pyqtSignal(str, str)             # (state, mood)
    sig_thought_updated = pyqtSignal(str)                # internal monologue
    sig_speech_updated = pyqtSignal(str)                 # character dialogue
    sig_telemetry_updated = pyqtSignal(str)              # action telemetry string
    sig_perception_updated = pyqtSignal(object, list)    # (QImage/QPixmap, list[UIElement])
    sig_targets_updated = pyqtSignal(list)               # list[UIElement]
    sig_targets_cleared = pyqtSignal()                   # clear all HUD boxes
    sig_reticle_requested = pyqtSignal(int, int, int, int, str) # (x, y, duration_ms, target_id, label)
    sig_reticle_cleared = pyqtSignal()                   # cancel reticle immediately (abort)

    # --- GUI -> Background Worker Signals ---
    sig_goal_submitted = pyqtSignal(str)                 # user goal string
    sig_pause_toggled = pyqtSignal(bool)                 # is_paused
    sig_panic_triggered = pyqtSignal()                   # emergency abort requested
    sig_hud_toggled = pyqtSignal(bool)                   # show/hide HUD overlay
    sig_brain_mode_changed = pyqtSignal(str)             # "local_llm" | "browser_offload"

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._goal_queue: queue.Queue[str] = queue.Queue()
        # Connect goal submission to internal thread-safe queue
        self.sig_goal_submitted.connect(self._on_internal_goal_submitted)

    @pyqtSlot(str)
    def _on_internal_goal_submitted(self, goal: str) -> None:
        self._goal_queue.put(goal)

    # -----------------------------------------------------------------------
    # Background Thread Helper Methods (Thread-Safe Signal Emitters)
    # -----------------------------------------------------------------------

    def notify_state(self, state: str, mood: str = "Curious") -> None:
        """Update companion state and mood badge from any thread."""
        self.sig_state_changed.emit(state, mood)

    def notify_thought(self, thought: str) -> None:
        """Stream internal thought monologue to companion dock."""
        self.sig_thought_updated.emit(thought)

    def notify_speech(self, speech: str) -> None:
        """Stream character dialogue speech bubble to companion dock."""
        self.sig_speech_updated.emit(speech)

    def notify_telemetry(self, telemetry: str) -> None:
        """Update pending action telemetry."""
        self.sig_telemetry_updated.emit(telemetry)

    def notify_perception(self, preview_image: Any, elements: List[UIElement]) -> None:
        """Update perception preview thumbnail and detected element summary."""
        self.sig_perception_updated.emit(preview_image, elements)

    def set_hud_targets(self, elements: List[UIElement]) -> None:
        """Publish grounded UI elements to GhostHUD for Set-of-Mark overlay."""
        self.sig_targets_updated.emit(elements)

    def clear_hud_targets(self) -> None:
        """Remove all Set-of-Mark bounding boxes from GhostHUD."""
        self.sig_targets_cleared.emit()

    def show_reticle(
        self,
        x: int,
        y: int,
        duration_ms: int = 300,
        target_id: int = 0,
        label: str = "",
    ) -> None:
        """
        Request 300ms pre-click targeting reticle on GhostHUD.
        Can be plugged directly into MouseDriver as reticle_callback:
        MouseDriver(..., reticle_callback=bridge.show_reticle)
        """
        self.sig_reticle_requested.emit(x, y, duration_ms, target_id, label)

    def clear_reticle(self) -> None:
        """Immediately abort and remove the active reticle (e.g. on interrupt touch)."""
        self.sig_reticle_cleared.emit()

    def get_next_goal(self, timeout_sec: Optional[float] = None) -> Optional[str]:
        """
        Thread-safe blocking or polling getter for background engine
        to retrieve the next user goal submitted from the GUI.
        """
        try:
            return self._goal_queue.get(timeout=timeout_sec)
        except queue.Empty:
            return None
```

### 2.4 Wiring `UIBridge` to Widgets
In `main.py` (or test fixtures):
```python
bridge = UIBridge()
dock = CompanionDock(config=app_config.ui.dock, bridge=bridge)
hud = GhostHUD(config=app_config.ui.hud, bridge=bridge)

# Connect bridge signals to dock slots (QueuedConnection guarantees main thread execution)
bridge.sig_state_changed.connect(dock.update_state, Qt.ConnectionType.QueuedConnection)
bridge.sig_thought_updated.connect(dock.update_thought, Qt.ConnectionType.QueuedConnection)
bridge.sig_speech_updated.connect(dock.update_speech, Qt.ConnectionType.QueuedConnection)
bridge.sig_telemetry_updated.connect(dock.update_telemetry, Qt.ConnectionType.QueuedConnection)
bridge.sig_perception_updated.connect(dock.update_perception_preview, Qt.ConnectionType.QueuedConnection)

# Connect bridge signals to HUD slots
bridge.sig_targets_updated.connect(hud.set_targets, Qt.ConnectionType.QueuedConnection)
bridge.sig_targets_cleared.connect(hud.clear_targets, Qt.ConnectionType.QueuedConnection)
bridge.sig_reticle_requested.connect(hud.show_reticle, Qt.ConnectionType.QueuedConnection)
bridge.sig_reticle_cleared.connect(hud.clear_reticle, Qt.ConnectionType.QueuedConnection)
bridge.sig_hud_toggled.connect(hud.setVisible, Qt.ConnectionType.QueuedConnection)

# Connect dock user actions to bridge signals
dock.sig_goal_submitted.connect(bridge.sig_goal_submitted)
dock.sig_pause_toggled.connect(bridge.sig_pause_toggled)
dock.sig_panic_triggered.connect(bridge.sig_panic_triggered)
dock.sig_hud_toggled.connect(bridge.sig_hud_toggled)
dock.sig_brain_mode_changed.connect(bridge.sig_brain_mode_changed)

# Wire MouseDriver to show reticle preview via bridge
mouse_driver = MouseDriver(
    config=app_config.hands.mouse,
    reticle_callback=lambda x, y, ms: bridge.show_reticle(x, y, ms),
)
```

---

## 3. UI Element Data Contracts & Types (`parasite_ai/ui/types.py`)

### 3.1 Data Model Specification: `UIElement`
The `UIElement` Pydantic model bridges perception (Milestone M4) and visual rendering (Milestone M3). It represents an indexed interactive control or OCR text box.

```python
"""
parasite_ai/ui/types.py - UI Element and Subsystem Data Contracts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field, computed_field


# Operational cognitive states
UIState = Literal[
    "WATCHING",      # Idling, observing screen, waiting for goal
    "THINKING",      # LLM reasoning / planning next step
    "DRIVING",       # Moving physical mouse or typing
    "USER_OVERRIDE", # Paused due to physical human touch (<2ms abort)
    "OFFLOADING",    # Interacting with Chrome web AI
    "PROTECTED",     # Sensitive window active; vision masked
]

# Character moods
UIMood = Literal[
    "Curious",
    "Focused",
    "Cautious",
    "Amused",
    "Panic-Averted",
    "Idle",
]

# State accent color palette (Hex codes)
STATE_COLORS: Dict[str, str] = {
    "WATCHING": "#10B981",       # Emerald Green
    "THINKING": "#F59E0B",       # Amber Orange
    "DRIVING": "#EF4444",        # Crimson Red
    "USER_OVERRIDE": "#06B6D4",  # Cyan Blue
    "OFFLOADING": "#8B5CF6",     # Electric Purple
    "PROTECTED": "#94A3B8",      # Steely Grey
}

# Set-of-Mark color theme by control role
SOM_ROLE_COLORS: Dict[str, str] = {
    "Button": "#00E5FF",         # Cyan
    "Edit": "#FF007F",           # Magenta
    "Hyperlink": "#3B82F6",      # Electric Blue
    "TabItem": "#3B82F6",        # Electric Blue
    "Text": "#F59E0B",           # Gold Amber (OCR)
    "Document": "#00E5FF",       # Cyan
    "MenuItem": "#00E5FF",       # Cyan
    "CheckBox": "#00E5FF",       # Cyan
    "RadioButton": "#00E5FF",    # Cyan
    "ComboBox": "#FF007F",       # Magenta
}


class UIElement(BaseModel):
    """
    Standard data contract representing a grounded desktop interactive element.
    Used by ScreenGrounder, GhostHUD, ActionDispatcher, and DualMindPipeline.
    """
    model_config = ConfigDict(extra="ignore", validate_default=True, frozen=True)

    id: int = Field(ge=1, description="1-based Set-of-Mark unique index [#1..#N].")
    role: str = Field(default="Button", description="Control role (Button, Edit, Text, etc.).")
    label: str = Field(default="", description="Accessible name or OCR text label.")
    x: int = Field(description="Top-left X coordinate in desktop pixel space.")
    y: int = Field(description="Top-left Y coordinate in desktop pixel space.")
    width: int = Field(ge=0, description="Element width in pixels.")
    height: int = Field(ge=0, description="Element height in pixels.")
    center_x: int = Field(description="Center target X coordinate for clicking.")
    center_y: int = Field(description="Center target Y coordinate for clicking.")
    source: Literal["uia", "ocr", "merged", "mock"] = Field(
        default="uia",
        description="Grounding origin source."
    )
    is_active_window: bool = Field(
        default=True,
        description="Whether element resides within the active foreground window."
    )

    @computed_field
    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        """Returns (x, y, width, height) tuple."""
        return (self.x, self.y, self.width, self.height)

    @computed_field
    @property
    def center(self) -> Tuple[int, int]:
        """Returns (center_x, center_y) click coordinate tuple."""
        return (self.center_x, self.center_y)

    @property
    def control_type(self) -> str:
        """Alias returning role for compatibility with PROJECT.md spec."""
        return self.role

    @classmethod
    def from_bbox(
        cls,
        id: int,
        bbox: Tuple[int, int, int, int],
        label: str = "",
        role: str = "Button",
        source: Literal["uia", "ocr", "merged", "mock"] = "uia",
        is_active_window: bool = True,
    ) -> UIElement:
        """Convenience constructor calculating centers automatically."""
        x, y, w, h = bbox
        return cls(
            id=id,
            role=role,
            label=label,
            x=x,
            y=y,
            width=w,
            height=h,
            center_x=x + w // 2,
            center_y=y + h // 2,
            source=source,
            is_active_window=is_active_window,
        )


# Alias for explicit target references
TargetElement = UIElement
```

---

## 4. High-DPI Awareness Initialization Pattern (`parasite_ai/ui/dpi.py`)

### 4.1 Problem: Coordinate Parity on Windows 11
Windows 11 commonly scales laptop and 4K displays to 125%, 150%, or 200%. If an application is DPI-unaware:
1. Windows DWM applies bitmap stretching, making the companion dock look blurry.
2. `mss` and `uiautomation` report bounding box coordinates in physical screen pixels (e.g. `(1500, 800)`).
3. If Qt uses virtual logical coordinates, drawing at `(1500, 800)` on a 150% scaled display places the box at physical `(2250, 1200)`, completely misaligning the Set-of-Mark tags and pre-click reticle from the real desktop controls!

### 4.2 The Solution & Fallback Chain
Windows provides three API generations for DPI awareness:
1. **Windows 10 1703+**: `user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4)`
2. **Windows 8.1+**: `shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE = 2)`
3. **Windows Vista+**: `user32.SetProcessDPIAware()`

**Critical Idempotency Finding**:
If DPI awareness is called a second time in the same process (such as when multiple test functions execute in pytest), Windows returns `E_ACCESSDENIED` (`0x80070005` or `-2147024891`), or `SetProcessDpiAwarenessContext` returns `0` with `GetLastError() == 5`. This must NOT raise an exception or fail!

```python
"""
parasite_ai/ui/dpi.py - High-DPI Awareness Bootstrapper.
Ensures 1:1 pixel coordinate parity between Windows physical display,
Win32 UI Automation, screen capture (mss), and PyQt6 overlays.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import sys


logger = logging.getLogger(__name__)


def init_high_dpi_awareness() -> bool:
    """
    Initializes Windows Per-Monitor v2 High-DPI awareness before QApplication startup.
    Idempotent and safe across multiple invocations, headless environments, and non-Windows OS.

    Returns:
        bool: True if DPI awareness is active (or already set), False on unsupported platforms.
    """
    if sys.platform != "win32":
        return False

    # 1. Primary: Windows 10 Creators Update 1703+ (Per-Monitor v2)
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        user32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
        DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
        if user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
            logger.debug("Initialized Per-Monitor v2 DPI Awareness via SetProcessDpiAwarenessContext.")
            return True
        # If returns False, check if it was already set (ERROR_ACCESS_DENIED = 5)
        err = ctypes.windll.kernel32.GetLastError()
        if err == 5:
            logger.debug("DPI awareness already configured for this process (ERROR_ACCESS_DENIED).")
            return True
    except (AttributeError, OSError) as e:
        logger.debug(f"SetProcessDpiAwarenessContext unavailable: {e}")

    # 2. Secondary: Windows 8.1+ (shcore.SetProcessDpiAwareness(2))
    try:
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness.restype = ctypes.c_long
        shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        hr = shcore.SetProcessDpiAwareness(2)
        # S_OK = 0, E_ACCESSDENIED = 0x80070005 (-2147024891)
        if hr == 0 or hr == -2147024891 or (hr & 0xFFFFFFFF) == 0x80070005:
            logger.debug("Initialized Per-Monitor DPI Awareness via shcore.SetProcessDpiAwareness.")
            return True
    except (AttributeError, OSError) as e:
        logger.debug(f"shcore.SetProcessDpiAwareness unavailable: {e}")

    # 3. Fallback: Windows Vista+ (user32.SetProcessDPIAware())
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware.restype = wintypes.BOOL
        return bool(user32.SetProcessDPIAware())
    except (AttributeError, OSError) as e:
        logger.debug(f"SetProcessDPIAware fallback failed: {e}")
        return False
```

---

## 5. Win32 Window Styles & Headless CI Compatibility (`parasite_ai/ui/win32_styles.py`)

### 5.1 Click-Through Extended Window Styles
The Ghost-Hand HUD overlay requires 5 Win32 extended window styles:
- `WS_EX_LAYERED (0x00080000)`: Enables per-pixel alpha transparency.
- `WS_EX_TRANSPARENT (0x00000020)`: Makes the window click-through (mouse clicks pass through to underlying desktop apps).
- `WS_EX_TOPMOST (0x00000008)`: Keeps overlay above all normal desktop windows.
- `WS_EX_NOACTIVATE (0x08000000)`: Prevents the overlay from stealing focus when drawn or clicked.
- `WS_EX_TOOLWINDOW (0x00000080)`: Hides overlay from Alt+Tab and taskbar.

### 5.2 Offscreen / Headless QPA Discovery
When running `pytest` under `QT_QPA_PLATFORM=offscreen`:
- `QWidget.winId()` returns `1` (an internal Qt handle, NOT a real Win32 HWND).
- Calling `user32.SetWindowLongW(1, ...)` fails with `ERROR_INVALID_WINDOW_HANDLE (1400)`.
- `ctypes.windll.user32.IsWindow(1)` returns `0` (`False`).
- Therefore, the helper MUST verify `user32.IsWindow(hwnd)` before calling `SetWindowLongW`!

```python
"""
parasite_ai/ui/win32_styles.py - Win32 Layered Window Style Helpers.
Safely configures click-through, topmost, non-activating window flags with headless CI guards.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from typing import Optional
from PyQt6.QtWidgets import QWidget


logger = logging.getLogger(__name__)

# Win32 Constants
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080

REQUIRED_HUD_EX_STYLES = (
    WS_EX_LAYERED
    | WS_EX_TRANSPARENT
    | WS_EX_TOPMOST
    | WS_EX_NOACTIVATE
    | WS_EX_TOOLWINDOW
)


def apply_click_through_styles(widget: QWidget) -> bool:
    """
    Applies Win32 click-through, topmost, non-activating extended styles to widget.
    Safely degrades on non-Windows platforms or in headless CI (offscreen QPA).

    Returns:
        bool: True if Win32 styles were successfully applied, False if skipped (headless/non-Windows).
    """
    if sys.platform != "win32":
        return False

    try:
        hwnd = int(widget.winId())
        user32 = ctypes.windll.user32

        # Check if hwnd is a valid native OS window handle (returns False in offscreen QPA)
        if not user32.IsWindow(hwnd):
            logger.debug(f"Skipping Win32 styles: winId {hwnd} is not a valid Win32 HWND (offscreen QPA).")
            return False

        current_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new_style = current_style | REQUIRED_HUD_EX_STYLES
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        logger.debug(f"Applied Win32 styles 0x{new_style:X} to HWND {hwnd}.")
        return True
    except Exception as e:
        logger.warning(f"Failed to apply Win32 extended window styles: {e}")
        return False
```

---

## 6. Package Layout & Exports (`parasite_ai/ui/__init__.py`)

### 6.1 Layout
```
parasite_ai/ui/
├── __init__.py           # Unified package exports
├── types.py              # UIElement, TargetElement, UIState, UIMood, color tables
├── dpi.py                # init_high_dpi_awareness()
├── win32_styles.py       # apply_click_through_styles(), Win32 constants
├── bridge.py             # UIBridge(QObject)
├── companion_dock.py     # CompanionDock(QWidget) [Explorer 1 spec]
└── ghost_hud.py          # GhostHUD(QWidget) [Explorer 2 spec]
```

### 6.2 Public Exports Specification (`parasite_ai/ui/__init__.py`)
```python
"""
ParasiteAI UI Subsystem - 100% Visible Desktop Companion Dock & Ghost-Hand Overlay.
"""

from parasite_ai.ui.types import (
    UIElement,
    TargetElement,
    UIState,
    UIMood,
    STATE_COLORS,
    SOM_ROLE_COLORS,
)
from parasite_ai.ui.dpi import init_high_dpi_awareness
from parasite_ai.ui.win32_styles import (
    apply_click_through_styles,
    GWL_EXSTYLE,
    WS_EX_LAYERED,
    WS_EX_TRANSPARENT,
    WS_EX_TOPMOST,
    WS_EX_NOACTIVATE,
    WS_EX_TOOLWINDOW,
    REQUIRED_HUD_EX_STYLES,
)
from parasite_ai.ui.bridge import UIBridge
from parasite_ai.ui.companion_dock import CompanionDock
from parasite_ai.ui.ghost_hud import GhostHUD

__all__ = [
    "UIElement",
    "TargetElement",
    "UIState",
    "UIMood",
    "STATE_COLORS",
    "SOM_ROLE_COLORS",
    "init_high_dpi_awareness",
    "apply_click_through_styles",
    "GWL_EXSTYLE",
    "WS_EX_LAYERED",
    "WS_EX_TRANSPARENT",
    "WS_EX_TOPMOST",
    "WS_EX_NOACTIVATE",
    "WS_EX_TOOLWINDOW",
    "REQUIRED_HUD_EX_STYLES",
    "UIBridge",
    "CompanionDock",
    "GhostHUD",
]
```

---

## 7. Complete Test Suite Architecture (`tests/`)

The test architecture leverages `pytest-qt` (`qtbot`) with headless `QT_QPA_PLATFORM=offscreen`.

### 7.1 Test Suite 1: `tests/test_companion_dock.py`

| # | Test Function | Target Feature | Verification Criteria |
|---|---|---|---|
| 1 | `test_dock_initialization_and_window_flags` | Window flags & config | Verifies `WindowStaysOnTopHint`, `FramelessWindowHint`, `Tool`, default dimensions 340x540px. |
| 2 | `test_dock_screen_anchoring` | Screen geometry calculation | Verifies bottom-right anchoring with 24px margins against `availableGeometry()`. |
| 3 | `test_dock_state_transitions` | 6 Operational States | Cycles `WATCHING`, `THINKING`, `DRIVING`, `USER_OVERRIDE`, `OFFLOADING`, `PROTECTED`; verifies badge text and accent color update. |
| 4 | `test_dock_mood_updates` | Character Mood | Updates mood to `Curious`, `Focused`, `Panic-Averted`; verifies mood pill label text. |
| 5 | `test_dock_speech_bubble_streaming` | Speech Dialogue | Sets single-line and multiline dialogue; verifies label text, word wrap, and rich styling. |
| 6 | `test_dock_internal_thought_stream` | Internal Monologue | Updates thought stream; verifies italic styling, monospace font, and auto-scroll behavior. |
| 7 | `test_dock_goal_submission_send_button` | User Input & Send Button | Enters goal text, clicks Send; verifies `sig_goal_submitted` emitted with goal text, and input cleared. |
| 8 | `test_dock_goal_submission_enter_key` | User Input & Enter Key | Enters goal text, presses `Qt.Key.Key_Return`; verifies `sig_goal_submitted` emitted and input cleared. |
| 9 | `test_dock_empty_goal_ignored` | Input Validation | Submits whitespace string `"   "`; verifies `sig_goal_submitted` is NOT emitted. |
| 10 | `test_dock_pause_toggle_button` | Pause/Resume Control | Clicks Pause; verifies `sig_pause_toggled(True)` emitted and button text becomes "Resume". Clicks again; verifies `False`. |
| 11 | `test_dock_panic_button_signal` | Emergency Panic Control | Clicks Panic button; verifies `sig_panic_triggered` emitted immediately. |
| 12 | `test_dock_hud_toggle_checkbox` | HUD Visibility Control | Toggles HUD checkbox; verifies `sig_hud_toggled` emitted with boolean state. |
| 13 | `test_dock_brain_mode_toggle` | Brain Mode Selection | Switches mode between `browser_offload` and `local_llm`; verifies `sig_brain_mode_changed` signal. |
| 14 | `test_dock_perception_preview_and_privacy_mask` | Perception Thumbnail | Pass test `QPixmap`; verifies thumbnail displayed. Transition to `PROTECTED`; verifies privacy mask blackout banner replaces thumbnail. |
| 15 | `test_dock_mouse_drag_repositioning` | Custom Title Bar Grip | Simulates `mousePressEvent` on title bar and `mouseMoveEvent`; verifies window moves by mouse delta. |

### 7.2 Test Suite 2: `tests/test_ghost_hud.py`

| # | Test Function | Target Feature | Verification Criteria |
|---|---|---|---|
| 1 | `test_ghost_hud_translucent_and_mouse_transparent` | Overlay Window Attributes | Verifies `WA_TranslucentBackground` and `WA_TransparentForMouseEvents` are True. |
| 2 | `test_ghost_hud_virtual_geometry_coverage` | Multi-Monitor Desktop Span | Verifies HUD geometry matches `primaryScreen().virtualGeometry()` (e.g. 3840x1080). |
| 3 | `test_ghost_hud_win32_styles_application` | Click-Through Win32 Styles | Mocks `SetWindowLongW`; verifies `WS_EX_LAYERED`, `WS_EX_TRANSPARENT`, `WS_EX_TOPMOST`, `WS_EX_NOACTIVATE`, `WS_EX_TOOLWINDOW` applied. |
| 4 | `test_ghost_hud_headless_safe_initialization` | Offscreen Headless Safety | Instantiates HUD under offscreen QPA; verifies `IsWindow(1)` guard prevents 1400 errors. |
| 5 | `test_ghost_hud_set_targets` | Set-of-Mark Target Ingestion | Passes list of `UIElement` instances; verifies `targets` stored and `update()` scheduled. |
| 6 | `test_ghost_hud_som_category_colors` | Visual Tag Color Coding | Verifies Buttons use `#00E5FF`, Edits use `#FF007F`, OCR text uses `#F59E0B`, Links use `#3B82F6`. |
| 7 | `test_ghost_hud_som_pill_badge_geometry` | Tag Label Badge Geometry | Verifies badge positioning `[#ID: Label]` sits at element top-left with padding. |
| 8 | `test_ghost_hud_som_render_execution` | QPainter Rendering Pipeline | Calls `hud.render(pixmap)` under `qtbot`; verifies zero paint exceptions with 50+ elements. |
| 9 | `test_ghost_hud_reticle_300ms_countdown` | Pre-Click Reticle Animation | Calls `show_reticle(300, 200, 300)`; verifies reticle active, timer triggers countdown, and `sig_reticle_completed` emitted after 300ms. |
| 10 | `test_ghost_hud_reticle_instant_abort` | Sub-2ms Interrupt Abort | Calls `clear_reticle()` mid-countdown; verifies reticle immediately cleared and timer stopped. |
| 11 | `test_ghost_hud_bezier_trajectory_preview` | Kinematic Path Preview | Verifies Bézier arc formula matches `KinematicsEngine` asymmetric control points from cursor to target. |
| 12 | `test_ghost_hud_clear_targets` | Screen Cleanup | Calls `clear_targets()`; verifies `targets` list emptied and overlay repainted blank. |

### 7.3 Test Suite 3: `tests/test_ui_bridge.py`

| # | Test Function | Target Feature | Verification Criteria |
|---|---|---|---|
| 1 | `test_ui_bridge_cross_thread_state_notification` | Thread-Safe State Signals | Emits `notify_state("DRIVING", "Focused")` from `threading.Thread`; verifies slot receives on main thread. |
| 2 | `test_ui_bridge_cross_thread_reticle_request` | Thread-Safe Reticle Preview | Calls `show_reticle(500, 400, 300)` from background thread; verifies signal received by HUD slot. |
| 3 | `test_ui_bridge_goal_queue_consumption` | Bi-Directional Queue | Emits `sig_goal_submitted("find file")`; background thread calls `bridge.get_next_goal(timeout_sec=0.5)` and retrieves string. |
| 4 | `test_ui_bridge_targets_signal` | Element List Marshalling | Emits `set_hud_targets([elem1, elem2])` across threads; verifies intact `UIElement` objects received. |

### 7.4 Test Suite 4: `tests/test_dpi.py`

| # | Test Function | Target Feature | Verification Criteria |
|---|---|---|---|
| 1 | `test_init_high_dpi_awareness_success` | Windows DPI Bootstrap | Calls `init_high_dpi_awareness()`; verifies returns `True` on Windows host. |
| 2 | `test_init_high_dpi_awareness_idempotency` | Multiple Invocations | Calls `init_high_dpi_awareness()` twice; verifies second call returns `True` without error. |
| 3 | `test_init_high_dpi_non_windows_fallback` | Platform Portability | Mocks `sys.platform = "linux"`; verifies returns `False` gracefully without throwing exceptions. |

---

## 8. Implementation Checklist & Worker Handoff Sequence

When the milestone implementation worker executes Milestone M3, they should follow this exact sequence:

1. **Step 1: Foundational Types & Helpers (`parasite_ai/ui/types.py`, `dpi.py`, `win32_styles.py`)**
   - Create `parasite_ai/ui/types.py` with `UIElement`, `TargetElement`, `UIState`, `UIMood`, `STATE_COLORS`, `SOM_ROLE_COLORS`.
   - Create `parasite_ai/ui/dpi.py` with `init_high_dpi_awareness()`.
   - Create `parasite_ai/ui/win32_styles.py` with `apply_click_through_styles()`.
   - Run unit tests: `tests/test_dpi.py`.

2. **Step 2: Cross-Thread Signal Bridge (`parasite_ai/ui/bridge.py`)**
   - Implement `UIBridge` with all background-to-GUI and GUI-to-background signals.
   - Run unit tests: `tests/test_ui_bridge.py`.

3. **Step 3: Desktop Companion Dock (`parasite_ai/ui/companion_dock.py`)**
   - Implement `CompanionDock` per Explorer 1 specification: frameless, always-on-top, state badges, thought stream, dialogue bubble, telemetry, perception thumbnail, interactive controls.
   - Run unit tests: `tests/test_companion_dock.py`.

4. **Step 4: Ghost-Hand Screen Overlay HUD (`parasite_ai/ui/ghost_hud.py`)**
   - Implement `GhostHUD` per Explorer 2 specification: virtual desktop geometry, click-through Win32 styles, Set-of-Mark boxes, 300ms reticle animation, Bézier path preview.
   - Run unit tests: `tests/test_ghost_hud.py`.

5. **Step 5: Package Exports (`parasite_ai/ui/__init__.py`)**
   - Export all public classes and functions in `parasite_ai/ui/__init__.py`.
   - Run full test suite: `uv run pytest tests/test_companion_dock.py tests/test_ghost_hud.py tests/test_ui_bridge.py tests/test_dpi.py -v`.
   - Verify 100% test pass rate with zero regression on all 321 existing tests.
