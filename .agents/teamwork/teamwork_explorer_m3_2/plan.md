# Milestone M3 Technical Implementation Plan: Ghost-Hand Screen Overlay HUD

**Author**: `teamwork_explorer_m3_2`  
**Target Module**: `parasite_ai/ui/ghost_hud.py`  
**Test Module**: `tests/test_ghost_hud.py`  
**Status**: APPROVED IMPLEMENTATION SPECIFICATION  

---

## 1. Executive Summary & Architectural Scope

ParasiteAI operates on the user's physical desktop under a strict **100% visible, desktop-native philosophy**. To ensure user transparency, trust, and predictability without interfering with desktop interactivity:
1. **The Ghost-Hand HUD (`parasite_ai/ui/ghost_hud.py`)** renders directly over the physical Windows desktop as a **hardware-level click-through transparent Win32 layered overlay**.
2. When screen grounding identifies interactive controls, the HUD renders **Set-of-Mark (SoM) bounding boxes `[#1..#N]`** with distinct role-based color themes and high-contrast pill badges.
3. Before any physical mouse click or trajectory sweep is performed, the HUD executes a **300ms pre-click targeting reticle preview**:
   - An animated contracting targeting reticle at `(target_x, target_y)`.
   - A floating aiming badge: `Aiming: [#ID] {label} Click in {remaining_ms}ms`.
   - A dynamic curved Bézier trajectory preview from current cursor position `(cur_x, cur_y)` to `(target_x, target_y)`.
4. If a human user touches the physical mouse during this 300ms window, the interrupt guard immediately cancels the pending action and aborts the HUD reticle before the cursor moves or touches the target.
5. All functionality is designed for **headless CI testability** using `pytest-qt` (`qtbot`).

---

## 2. Window Architecture & Win32 Extended Styles

### 2.1 Geometry & Multi-Monitor Virtual Desktop Coverage
The HUD overlay must span the **entire virtual desktop**, accommodating multi-monitor configurations, negative coordinate offsets, and display topology changes:

```python
screen = QGuiApplication.primaryScreen()
virtual_geo = screen.virtualGeometry()
self.setGeometry(virtual_geo)
```

- **Origin Offset Handling**: Multi-monitor setups where secondary screens are situated above or to the left of the primary screen have negative desktop coordinates (e.g. `x = -1920`).
- The HUD window is positioned at `(virtual_geo.x(), virtual_geo.y())`.
- For `QPainter` drawing within the HUD widget, desktop coordinates `(x, y)` are translated to widget-local coordinates via:
  ```python
  def _to_local(self, x: int, y: int) -> QPoint:
      geo = self.geometry()
      return QPoint(x - geo.x(), y - geo.y())
  ```
- **Dynamic Topology Changes**: Connect to `screen.virtualGeometryChanged` to resize and reposition automatically if resolution or monitor setup changes during runtime.

### 2.2 Win32 Extended Styles (`GWL_EXSTYLE`)
The window must be 100% transparent to mouse events, never steal input focus, remain permanently on top, and never appear in the Alt+Tab switcher or Windows taskbar.

#### Required Win32 Extended Styles:
| Constant | Hex Value | Decimal | Operational Purpose |
|---|---|---|---|
| `WS_EX_LAYERED` | `0x00080000` | 524288 | Enables per-pixel alpha transparency and hardware compositing. |
| `WS_EX_TRANSPARENT` | `0x00000020` | 32 | **Click-through**: Hardware mouse clicks pass straight through the window to whatever is beneath it. |
| `WS_EX_TOPMOST` | `0x00000008` | 8 | Window is placed above all non-topmost windows and stays above them even when deactivated. |
| `WS_EX_NOACTIVATE` | `0x08000000` | 134217728 | The window is never activated on click or display; foreground focus remains with target applications. |
| `WS_EX_TOOLWINDOW` | `0x00000080` | 128 | Prevents the overlay from cluttering the Windows Taskbar and Alt+Tab application switcher. |

#### Qt Window Flags and Attributes:
```python
self.setWindowFlags(
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.Tool
)
self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
```

#### Application Method (`apply_win32_styles`):
Applied on `self.winId()` after window handle creation:
```python
def apply_win32_styles(self) -> bool:
    if sys.platform != "win32":
        return False
    try:
        hwnd = int(self.winId())
        if not hwnd:
            return False
        user32 = ctypes.windll.user32
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_TOPMOST = 0x00000008
        WS_EX_NOACTIVATE = 0x08000000
        WS_EX_TOOLWINDOW = 0x00000080

        old_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new_style = old_style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)

        # Enforce topmost z-order and apply style change without activating
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
        SWP_FRAMECHANGED = 0x0020
        HWND_TOPMOST = -1
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        return True
    except Exception as exc:
        logger.warning(f"Failed to apply Win32 overlay styles: {exc}")
        return False
```

---

## 3. Set-of-Mark (SoM) Visual Rendering Engine

### 3.1 UI Element Representation & Normalization
`GhostHUD.set_targets(targets: list[Any])` accepts:
- Pydantic `UIElement` instances
- Dictionaries with keys `id`, `role`/`control_type`, `label`, `x`, `y`, `width`, `height`, `center_x`, `center_y`
- Duck-typed objects with attributes

A normalization helper `_normalize_target(raw)` guarantees consistent internal structures:
```python
@dataclass
class HUDTarget:
    id: int
    role: str
    label: str
    x: int
    y: int
    width: int
    height: int
    center_x: int
    center_y: int
    color_hex: str
```

### 3.2 Role-Based Color Palette Mapping
Category themes are chosen for maximum visual contrast against diverse desktop wallpapers and application themes:
| Element Category / Control Type | Theme Color | Hex Code | Visual Meaning |
|---|---|---|---|
| **Buttons & Clickable Controls** (`Button`, `MenuItem`, `SplitButton`, `RadioButton`, `CheckBox`) | Neon Cyan | `#00E5FF` | Direct invocation target |
| **Text Inputs & Edits** (`Edit`, `ComboBox`, `Input`, `TextBox`, `Document`) | Hot Magenta | `#FF007F` | Text insertion / typing destination |
| **OCR Text Fallbacks** (`OCR`, `Text`, `Label`) | Gold Amber | `#F59E0B` | Visual text detected without UIA control structure |
| **Hyperlinks & Navigation** (`Hyperlink`, `Link`, `TabItem`) | Electric Blue | `#3B82F6` | Page or tab navigation |
| **Generic / Unclassified** | Mint Green | `#10B981` | Fallback control |

### 3.3 Visual Bounding Box Rendering
- **Box Fill**: `QColor(color_hex)` with `box_alpha` (default `0.20` - `0.25`, configurable via `GhostHUDConfig`).
- **Box Border**: `QPen(QColor(color_hex), stroke_width)` (default `1.5px`).
- **Corner Curvature**: Subtle rounded rect radius `3.0px` for modern aesthetic.
- **Render Hints**: `QPainter.RenderHint.Antialiasing` enabled.

### 3.4 High-Contrast Rounded Pill Badges
- **Text Format**: `[#ID]` or `[#ID: Label]` (label truncated to 16 chars with `…` if long).
- **Positioning**: Top-left corner `(box_x, box_y - badge_height - 2)`.
  - **Screen Boundary Guard**: If `box_y - badge_height - 2 < vgeom.y()`, position badge inside the box at `(box_x + 2, box_y + 2)` so it never clips off-screen.
  - If `box_x + badge_width > vgeom.right()`, shift left to remain fully visible.
- **Pill Background**: Dark slate card (`#111827`, alpha 230 / 90% opacity).
- **Pill Border**: 1.0px hairline stroke matching the element's category theme color.
- **Pill Font**: `Segoe UI` or `Consolas`, 8.5pt, bold, crisp white `#FFFFFF`.
- **Pill Padding**: 6px horizontal padding, 2px vertical padding, border radius 4.0px.

---

## 4. 300ms Pre-Click Targeting Reticle & Path Preview Engine

### 4.1 Reticle Animation State Machine
- When `show_reticle(x, y, duration_ms=300, target_id=None, label=None)` is called:
  1. Capture start position `(start_x, start_y) = (QCursor.pos().x(), QCursor.pos().y())`.
  2. Record target position `(target_x, target_y)`.
  3. Store `target_id` and `label`.
  4. Start high-resolution elapsed timer (`QElapsedTimer`).
  5. Start 60 FPS animation timer (`QTimer` at 16ms interval).
  6. Set `_reticle_active = True`.
  7. Emit `sig_reticle_started(x, y, duration_ms)`.
- During each 16ms tick (`_on_animation_tick`):
  - `elapsed_ms = elapsed_timer.elapsed()`
  - `progress = min(1.0, elapsed_ms / duration_ms)`
  - `remaining_ms = max(0, duration_ms - elapsed_ms)`
  - Call `self.update()`.
  - If `elapsed_ms >= duration_ms`:
    - Stop animation timer.
    - Set `_reticle_active = False`.
    - Emit `sig_reticle_finished(target_x, target_y)`.
    - Call `self.update()`.

### 4.2 Sci-Fi Targeting Brackets & Crosshair Geometry
- Centered at `(target_x, target_y)`.
- **Contracting Corner Brackets**: 4 corner brackets `⌜ ⌝ ⌞ ⌟`.
  - Initial radius at `progress = 0.0`: `32px`.
  - Final locked radius at `progress = 1.0`: `16px`.
  - Ease-out formula: `current_radius = 16.0 + 16.0 * ((1.0 - progress) ** 2)`.
  - Bracket arm length: `7px`.
  - Bracket stroke: `2.5px`, color `#FF3366` (or `config.reticle_color`).
  - Outer glow halo: Semi-transparent circular ring at `current_radius + 4px` with 30% alpha.
- **Center Precision Crosshair**:
  - Central targeting dot: radius 1.5px.
  - 4 crosshair ticks extending from `r = 3px` to `r = 8px`.

### 4.3 Floating Aiming Banner
- Renders a floating notification pill directly above the targeting reticle:
  - Text: `f"Aiming: [#{target_id}] {truncated_label} ({remaining_ms}ms)"` if ID and label present;
    or `f"Aiming: [#{target_id}] ({remaining_ms}ms)"`;
    or `f"Aiming: Click in {remaining_ms}ms"`.
  - Position: Horizontally centered above target at `target_y - current_radius - 22`.
  - Pill styling: Dark background `#0F172A` (92% opacity), 1.5px glowing border `#FF3366`, 9pt bold text `#F8FAFC`.
  - Screen boundary clamp: If `target_y - current_radius - 22 < vgeom.y()`, flips below reticle to `target_y + current_radius + 8`.

### 4.4 Dynamic Curved Bézier Trajectory Preview
- Previews the exact kinematic path the mouse cursor will travel.
- From physical cursor `p0 = (start_x, start_y)` to `p3 = (target_x, target_y)`.
- If distance `dist = hypot(target_x - start_x, target_y - start_y) > 15`:
  - Vector: `vx = target_x - start_x`, `vy = target_y - start_y`.
  - Normal: `nx = -vy / dist`, `ny = vx / dist`.
  - Subtle curvature: `arc_amp = dist * 0.12`.
  - Kinematic control points matching `KinematicsEngine`:
    `p1 = (start_x + 0.32 * vx + arc_amp * nx, start_y + 0.32 * vy + arc_amp * ny)`
    `p2 = (start_x + 0.68 * vx + 0.45 * arc_amp * nx, start_y + 0.68 * vy + 0.45 * arc_amp * ny)`
  - Render with `QPainterPath.cubicTo(p1.x, p1.y, p2.x, p2.y, p3.x, p3.y)`.
  - Path Pen: Neon cyan/pink glowing dashed pen: `QPen(QColor(0, 229, 255, 170), 2.0, Qt.PenStyle.DashLine)`.
  - **Animated Pulse Orb**: A luminous orb travels along the Bézier curve in real-time as `progress` increases:
    ```python
    u = 1.0 - progress
    bx = (u**3)*p0[0] + 3*(u**2)*progress*p1[0] + 3*u*(progress**2)*p2[0] + (progress**3)*p3[0]
    by = (u**3)*p0[1] + 3*(u**2)*progress*p1[1] + 3*u*(progress**2)*p2[1] + (progress**3)*p3[1]
    ```
    Drawn as a glowing dot (radius 3.5px) with white center and cyan halo.

### 4.5 Clean Timeout & Abort Handling
- `clear_reticle()` or `abort_reticle()`:
  - Immediately stops the animation timer.
  - Sets `_reticle_active = False`.
  - Emits `sig_reticle_aborted()`.
  - Calls `self.update()`.
- Upon interrupt abort (`cancellation_token` set by `InterruptGuard`), this method is called to vanish the targeting reticle in < 1ms.

---

## 5. Complete Production Specification for `parasite_ai/ui/ghost_hud.py`

```python
"""
ParasiteAI - Ghost-Hand Screen Overlay HUD.
Transparent, click-through Win32 layered overlay rendering Set-of-Mark (SoM)
numbered bounding boxes, category color badges, and a 300ms pre-click targeting reticle
with kinematic curved Bezier path preview.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import logging
import math
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from PyQt6.QtCore import (
    QElapsedTimer,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QTimer,
    Qt,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import QWidget

from parasite_ai.config import GhostHUDConfig

logger = logging.getLogger(__name__)

# Win32 Constants
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080

SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
HWND_TOPMOST = -1

# Category Color Mapping
ROLE_COLOR_MAP: Dict[str, str] = {
    # Buttons & Clickables -> Neon Cyan
    "button": "#00E5FF",
    "buttoncontrol": "#00E5FF",
    "splitbutton": "#00E5FF",
    "menuitem": "#00E5FF",
    "menuitemcontrol": "#00E5FF",
    "radiobutton": "#00E5FF",
    "checkbox": "#00E5FF",
    # Text Inputs -> Hot Magenta
    "edit": "#FF007F",
    "editcontrol": "#FF007F",
    "combobox": "#FF007F",
    "comboboxcontrol": "#FF007F",
    "input": "#FF007F",
    "textbox": "#FF007F",
    "document": "#FF007F",
    "documentcontrol": "#FF007F",
    # OCR Fallback -> Gold Amber
    "ocr": "#F59E0B",
    "text": "#F59E0B",
    "textcontrol": "#F59E0B",
    "label": "#F59E0B",
    # Links & Tabs -> Electric Blue
    "link": "#3B82F6",
    "hyperlink": "#3B82F6",
    "hyperlinkcontrol": "#3B82F6",
    "tabitem": "#3B82F6",
    "tabitemcontrol": "#3B82F6",
}


@dataclass
class HUDTarget:
    """Internal normalized representation of a grounded UI element."""
    id: int
    role: str
    label: str
    x: int
    y: int
    width: int
    height: int
    center_x: int
    center_y: int
    color_hex: str


class GhostHUD(QWidget):
    """
    Transparent click-through Win32 layered screen overlay.
    Spans full virtual desktop and renders Set-of-Mark tags and 300ms pre-click reticle.
    """

    # Qt Signals for decoupled thread-safe communication
    sig_targets_updated = pyqtSignal(int)                         # count of targets
    sig_reticle_started = pyqtSignal(int, int, int)              # x, y, duration_ms
    sig_reticle_finished = pyqtSignal(int, int)                  # x, y
    sig_reticle_aborted = pyqtSignal()
    sig_hud_cleared = pyqtSignal()

    def __init__(
        self,
        config: Optional[GhostHUDConfig] = None,
        parent: Optional[QWidget] = None,
        enable_win32_styles: bool = True,
    ) -> None:
        super().__init__(parent)
        self.config = config or GhostHUDConfig()
        self._enabled: bool = self.config.enabled
        self._enable_win32_styles: bool = enable_win32_styles

        # Target Set-of-Mark state
        self._targets: List[HUDTarget] = []

        # Reticle animation state
        self._reticle_active: bool = False
        self._reticle_target: QPoint = QPoint(0, 0)
        self._reticle_start: QPoint = QPoint(0, 0)
        self._reticle_id: Optional[int] = None
        self._reticle_label: Optional[str] = None
        self._reticle_duration_ms: int = self.config.reticle_duration_ms
        self._elapsed_timer = QElapsedTimer()

        # Animation timer
        self._anim_timer = QTimer(self)
        fps = max(15, min(144, self.config.fps_target))
        self._anim_timer.setInterval(max(5, int(1000 / fps)))
        self._anim_timer.timeout.connect(self._on_animation_tick)

        # Fonts & styling
        self._badge_font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        self._banner_font = QFont("Segoe UI", 9, QFont.Weight.Bold)

        self._init_window()

    def _init_window(self) -> None:
        """Sets frameless, transparent, tool, and topmost Qt flags."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self._update_geometry()

        # Listen for screen topology changes
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen.virtualGeometryChanged.connect(self._on_virtual_geometry_changed)

    def _update_geometry(self) -> None:
        """Spans the entire virtual desktop."""
        screen = QGuiApplication.primaryScreen()
        if screen:
            vgeom = screen.virtualGeometry()
            self.setGeometry(vgeom)

    def _on_virtual_geometry_changed(self, rect: QRect) -> None:
        self.setGeometry(rect)
        self.update()

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if self._enable_win32_styles:
            self.apply_win32_styles()

    def apply_win32_styles(self) -> bool:
        """Applies hardware click-through, layered, and no-activate styles."""
        if sys.platform != "win32":
            return False
        try:
            hwnd = int(self.winId())
            if not hwnd:
                return False
            user32 = ctypes.windll.user32
            old_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = (
                old_style
                | WS_EX_LAYERED
                | WS_EX_TRANSPARENT
                | WS_EX_TOPMOST
                | WS_EX_NOACTIVATE
                | WS_EX_TOOLWINDOW
            )
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            user32.SetWindowPos(
                hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED
            )
            return True
        except Exception as exc:
            logger.warning(f"Failed to apply Win32 overlay styles: {exc}")
            return False

    # -----------------------------------------------------------------------
    # Public API / Slots
    # -----------------------------------------------------------------------
    @pyqtSlot(list)
    def set_targets(self, targets: List[Any]) -> None:
        """Populates grounded UI elements for Set-of-Mark visual rendering."""
        normalized: List[HUDTarget] = []
        for raw in targets:
            norm = self._normalize_target(raw)
            if norm:
                normalized.append(norm)
        self._targets = normalized
        self.sig_targets_updated.emit(len(self._targets))
        self.update()

    @pyqtSlot(int, int)
    @pyqtSlot(int, int, int)
    @pyqtSlot(int, int, int, object, object)
    def show_reticle(
        self,
        x: int,
        y: int,
        duration_ms: Optional[int] = None,
        target_id: Optional[int] = None,
        label: Optional[str] = None,
    ) -> None:
        """Initiates animated targeting reticle, aiming banner, and trajectory preview."""
        self._reticle_target = QPoint(x, y)
        self._reticle_start = QCursor.pos()
        self._reticle_id = target_id
        self._reticle_label = label
        self._reticle_duration_ms = (
            duration_ms if duration_ms is not None else self.config.reticle_duration_ms
        )

        self._reticle_active = True
        self._elapsed_timer.restart()
        self._anim_timer.start()
        self.sig_reticle_started.emit(x, y, self._reticle_duration_ms)
        self.update()

    @pyqtSlot()
    def abort_reticle(self) -> None:
        """Immediately halts and clears targeting reticle on interrupt/panic."""
        if self._reticle_active:
            self._anim_timer.stop()
            self._reticle_active = False
            self.sig_reticle_aborted.emit()
            self.update()

    @pyqtSlot()
    def clear_reticle(self) -> None:
        """Alias for abort_reticle."""
        self.abort_reticle()

    @pyqtSlot()
    def clear_targets(self) -> None:
        """Clears all Set-of-Mark bounding boxes."""
        self._targets.clear()
        self.sig_targets_updated.emit(0)
        self.update()

    @pyqtSlot()
    def clear_all(self) -> None:
        """Clears both targets and active reticle."""
        self._targets.clear()
        self.abort_reticle()
        self.sig_hud_cleared.emit()
        self.update()

    def set_hud_enabled(self, enabled: bool) -> None:
        """Toggles HUD visibility."""
        self._enabled = enabled
        self.update()

    # -----------------------------------------------------------------------
    # Animation Tick
    # -----------------------------------------------------------------------
    def _on_animation_tick(self) -> None:
        if not self._reticle_active:
            self._anim_timer.stop()
            return

        elapsed = self._elapsed_timer.elapsed()
        if elapsed >= self._reticle_duration_ms:
            self._anim_timer.stop()
            self._reticle_active = False
            self.sig_reticle_finished.emit(self._reticle_target.x(), self._reticle_target.y())

        self.update()

    # -----------------------------------------------------------------------
    # Normalization & Coordinates
    # -----------------------------------------------------------------------
    def _normalize_target(self, raw: Any) -> Optional[HUDTarget]:
        try:
            if isinstance(raw, dict):
                tid = int(raw.get("id", 0))
                role = str(raw.get("role") or raw.get("control_type") or "Button")
                label = str(raw.get("label") or raw.get("name") or "")
                x = int(raw.get("x", 0))
                y = int(raw.get("y", 0))
                w = int(raw.get("width", 0))
                h = int(raw.get("height", 0))
                cx = int(raw.get("center_x", x + w // 2))
                cy = int(raw.get("center_y", y + h // 2))
            else:
                tid = int(getattr(raw, "id", 0))
                role = str(getattr(raw, "role", getattr(raw, "control_type", "Button")))
                label = str(getattr(raw, "label", getattr(raw, "name", "")))
                x = int(getattr(raw, "x", 0))
                y = int(getattr(raw, "y", 0))
                w = int(getattr(raw, "width", 0))
                h = int(getattr(raw, "height", 0))
                cx = int(getattr(raw, "center_x", x + w // 2))
                cy = int(getattr(raw, "center_y", y + h // 2))

            color_hex = ROLE_COLOR_MAP.get(role.lower(), self.config.som_box_color)
            return HUDTarget(
                id=tid,
                role=role,
                label=label,
                x=x,
                y=y,
                width=w,
                height=h,
                center_x=cx,
                center_y=cy,
                color_hex=color_hex,
            )
        except Exception:
            return None

    def _to_local(self, x: int, y: int) -> QPoint:
        geo = self.geometry()
        return QPoint(x - geo.x(), y - geo.y())

    # -----------------------------------------------------------------------
    # Painting
    # -----------------------------------------------------------------------
    def paintEvent(self, event: Any) -> None:
        if not self._enabled:
            return

        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

            # 1. Paint Set-of-Mark elements
            if self._targets:
                self._paint_som_elements(painter)

            # 2. Paint Reticle, Banner, and Trajectory
            if self._reticle_active:
                self._paint_reticle_and_path(painter)

    def _paint_som_elements(self, painter: QPainter) -> None:
        vgeom = self.geometry()
        box_alpha_int = max(0, min(255, int(255 * self.config.box_alpha)))
        stroke_w = self.config.stroke_width_px
        metrics = QFontMetrics(self._badge_font)

        for target in self._targets:
            local_pos = self._to_local(target.x, target.y)
            rect = QRectF(local_pos.x(), local_pos.y(), target.width, target.height)

            color = QColor(target.color_hex)
            fill_color = QColor(color.red(), color.green(), color.blue(), box_alpha_int)

            # Bounding box
            painter.setPen(QPen(color, stroke_w))
            painter.setBrush(fill_color)
            painter.drawRoundedRect(rect, 3.0, 3.0)

            # Pill Badge Text
            trunc_label = target.label[:14] + "…" if len(target.label) > 14 else target.label
            text = f"[#{target.id}: {trunc_label}]" if trunc_label else f"[#{target.id}]"

            tw = metrics.horizontalAdvance(text)
            th = metrics.height()
            pw = tw + 12
            ph = th + 4

            # Pill position: Above box, or inside box if at screen edge
            bx = local_pos.x()
            by = local_pos.y() - ph - 2
            if by < 0:
                by = local_pos.y() + 2
            if bx + pw > vgeom.width():
                bx = max(0, vgeom.width() - pw - 2)

            pill_rect = QRectF(bx, by, pw, ph)

            # Draw Pill Card
            painter.setPen(QPen(color, 1.0))
            painter.setBrush(QColor(17, 24, 39, 230))  # Slate-900 90% opacity
            painter.drawRoundedRect(pill_rect, 4.0, 4.0)

            # Draw Pill Text
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(self._badge_font)
            painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_reticle_and_path(self, painter: QPainter) -> None:
        elapsed = self._elapsed_timer.elapsed()
        duration = max(1, self._reticle_duration_ms)
        progress = max(0.0, min(1.0, elapsed / duration))
        remaining_ms = max(0, duration - elapsed)

        start_loc = self._to_local(self._reticle_start.x(), self._reticle_start.y())
        target_loc = self._to_local(self._reticle_target.x(), self._reticle_target.y())

        # 1. Dynamic Curved Bézier Trajectory Preview
        self._paint_bezier_path(painter, start_loc, target_loc, progress)

        # 2. Contracting Reticle Brackets & Center Crosshair
        self._paint_targeting_reticle(painter, target_loc, progress)

        # 3. Floating Aiming Banner
        self._paint_aiming_banner(painter, target_loc, remaining_ms)

    def _paint_bezier_path(
        self, painter: QPainter, p0: QPoint, p3: QPoint, progress: float
    ) -> None:
        dx = p3.x() - p0.x()
        dy = p3.y() - p0.y()
        dist = math.hypot(dx, dy)
        if dist < 15.0:
            return

        nx = -dy / dist
        ny = dx / dist
        arc_amp = dist * 0.12

        p1 = QPointF(p0.x() + 0.32 * dx + arc_amp * nx, p0.y() + 0.32 * dy + arc_amp * ny)
        p2 = QPointF(p0.x() + 0.68 * dx + 0.45 * arc_amp * nx, p0.y() + 0.68 * dy + 0.45 * arc_amp * ny)

        path = QPainterPath()
        path.moveTo(QPointF(p0.x(), p0.y()))
        path.cubicTo(p1, p2, QPointF(p3.x(), p3.y()))

        # Glowing dashed path
        pen = QPen(QColor(0, 229, 255, 175), 2.0, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Active pulse traveling orb along curve
        u = 1.0 - progress
        bx = (u**3)*p0.x() + 3*(u**2)*progress*p1.x() + 3*u*(progress**2)*p2.x() + (progress**3)*p3.x()
        by = (u**3)*p0.y() + 3*(u**2)*progress*p1.y() + 3*u*(progress**2)*p2.y() + (progress**3)*p3.y()

        # Orb halo + center dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 229, 255, 90))
        painter.drawEllipse(QPointF(bx, by), 6.0, 6.0)
        painter.setBrush(QColor(255, 255, 255, 230))
        painter.drawEllipse(QPointF(bx, by), 2.5, 2.5)

    def _paint_targeting_reticle(self, painter: QPainter, center: QPoint, progress: float) -> None:
        cx, cy = center.x(), center.y()
        reticle_color = QColor(self.config.reticle_color)

        # Dynamic contracting radius: from 32px down to 16px
        radius = 16.0 + 16.0 * ((1.0 - progress) ** 2)
        arm = 7.0

        # Pulsing outer ring
        pulse_alpha = int(70 * (1.0 - 0.5 * progress))
        painter.setPen(QPen(QColor(reticle_color.red(), reticle_color.green(), reticle_color.blue(), pulse_alpha), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), radius + 5.0, radius + 5.0)

        # 4 Corner brackets: Top-Left, Top-Right, Bottom-Left, Bottom-Right
        bracket_pen = QPen(reticle_color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap)
        painter.setPen(bracket_pen)

        # ⌜ Top-Left
        painter.drawLine(int(cx - radius), int(cy - radius), int(cx - radius + arm), int(cy - radius))
        painter.drawLine(int(cx - radius), int(cy - radius), int(cx - radius), int(cy - radius + arm))

        # ⌝ Top-Right
        painter.drawLine(int(cx + radius), int(cy - radius), int(cx + radius - arm), int(cy - radius))
        painter.drawLine(int(cx + radius), int(cy - radius), int(cx + radius), int(cy - radius + arm))

        # ⌞ Bottom-Left
        painter.drawLine(int(cx - radius), int(cy + radius), int(cx - radius + arm), int(cy + radius))
        painter.drawLine(int(cx - radius), int(cy + radius), int(cx - radius), int(cy + radius - arm))

        # ⌟ Bottom-Right
        painter.drawLine(int(cx + radius), int(cy + radius), int(cx + radius - arm), int(cy + radius))
        painter.drawLine(int(cx + radius), int(cy + radius), int(cx + radius), int(cy + radius - arm))

        # Center Crosshair ticks
        ch_pen = QPen(QColor(255, 255, 255, 210), 1.2)
        painter.setPen(ch_pen)
        painter.drawLine(cx - 7, cy, cx - 2, cy)
        painter.drawLine(cx + 2, cy, cx + 7, cy)
        painter.drawLine(cx, cy - 7, cx, cy - 2)
        painter.drawLine(cx, cy + 2, cx, cy + 7)

        # Center dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(reticle_color)
        painter.drawEllipse(QPointF(cx, cy), 1.5, 1.5)

    def _paint_aiming_banner(self, painter: QPainter, center: QPoint, remaining_ms: int) -> None:
        cx, cy = center.x(), center.y()
        reticle_color = QColor(self.config.reticle_color)
        metrics = QFontMetrics(self._banner_font)

        if self._reticle_id is not None and self._reticle_label:
            lbl = self._reticle_label[:12] + "…" if len(self._reticle_label) > 12 else self._reticle_label
            text = f"Aiming: [#{self._reticle_id}] {lbl} ({remaining_ms}ms)"
        elif self._reticle_id is not None:
            text = f"Aiming: [#{self._reticle_id}] Click in {remaining_ms}ms"
        else:
            text = f"Aiming: Click in {remaining_ms}ms"

        tw = metrics.horizontalAdvance(text)
        th = metrics.height()
        bw = tw + 16
        bh = th + 6

        # Position banner above reticle brackets
        bx = cx - bw // 2
        by = cy - 42
        if by < 0:
            by = cy + 24  # Flip below if at top edge

        banner_rect = QRectF(bx, by, bw, bh)

        # Card container
        painter.setPen(QPen(reticle_color, 1.5))
        painter.setBrush(QColor(15, 23, 42, 235))  # Deep midnight slate
        painter.drawRoundedRect(banner_rect, 5.0, 5.0)

        # Text
        painter.setPen(QColor(248, 250, 252))
        painter.setFont(self._banner_font)
        painter.drawText(banner_rect, Qt.AlignmentFlag.AlignCenter, text)
```

---

## 6. Thread Safety & Integration Architecture

### 6.1 Calling Contexts
1. **From `MouseDriver`**:
   `MouseDriver` in `parasite_ai/hands/mouse.py` invokes:
   ```python
   if preview_reticle and self.preview_reticle_ms > 0:
       if self.reticle_callback:
           self.reticle_callback(target_x, target_y, self.preview_reticle_ms)
   ```
   Binding `hud.show_reticle` directly to `MouseDriver.reticle_callback` works seamlessly.
2. **From Background Engine Thread**:
   When background threads (e.g. Cognitive loop or Perception loop) update targets or trigger reticle, they can either:
   - Call Qt slots directly if using `QMetaObject.invokeMethod`:
     ```python
     QMetaObject.invokeMethod(hud, "set_targets", Qt.ConnectionType.QueuedConnection, Q_ARG(list, targets))
     ```
   - Connect Qt signals via `sig_targets_updated`, `sig_reticle_requested`.
3. **From `InterruptGuard`**:
   When physical hardware touch aborts synthetic movement, the cancellation handler calls:
   ```python
   hud.abort_reticle()
   ```
   Clearing the reticle and trajectory in < 1ms.

---

## 7. Headless Testability & `pytest-qt` Verification Plan (`tests/test_ghost_hud.py`)

### 7.1 Test Strategy
- **Platform Agnostic & Headless Friendly**: Tests run seamlessly in both interactive Windows desktops and headless environments (`QT_QPA_PLATFORM=offscreen`).
- **Zero Real Clicks Intercepted**: Confirms that mouse events pass through the overlay.
- **Fast Deterministic Execution**: Reticle duration can be parameterized down to 30ms-50ms in unit tests so test suites complete in < 1 second.
- **Offscreen QPainter Rendering**: Renders widget directly to an in-memory `QPixmap` (`hud.render(pixmap)`), verifying every branch of `paintEvent` without graphical dependencies.

### 7.2 Detailed Test Cases in `tests/test_ghost_hud.py`

```python
"""
Tests for Ghost-Hand Screen Overlay HUD (parasite_ai/ui/ghost_hud.py).
Verifies Win32 extended styles, virtual desktop geometry, Set-of-Mark rendering,
color themes, 300ms reticle countdown, Bezier path calculation, and interrupt aborts.
"""

import sys
from unittest.mock import MagicMock, patch
import pytest
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QApplication

from parasite_ai.config import GhostHUDConfig
from parasite_ai.ui.ghost_hud import (
    GWL_EXSTYLE,
    ROLE_COLOR_MAP,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TOPMOST,
    WS_EX_TRANSPARENT,
    WS_EX_TOOLWINDOW,
    GhostHUD,
    HUDTarget,
)


@pytest.fixture
def hud_config():
    return GhostHUDConfig(
        enabled=True,
        fps_target=60,
        reticle_duration_ms=100,  # Fast 100ms for deterministic unit testing
        som_box_color="#00E5FF",
        box_alpha=0.25,
        stroke_width_px=1.5,
    )


class TestGhostHUDInitialization:
    def test_window_flags_and_attributes(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        flags = hud.windowFlags()
        assert bool(flags & Qt.WindowType.FramelessWindowHint)
        assert bool(flags & Qt.WindowType.WindowStaysOnTopHint)
        assert bool(flags & Qt.WindowType.Tool)

        assert hud.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert hud.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def test_virtual_desktop_geometry_span(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        screen = QApplication.primaryScreen()
        if screen:
            expected_geo = screen.virtualGeometry()
            assert hud.geometry() == expected_geo

    @pytest.mark.skipif(sys.platform != "win32", reason="Win32 specific test")
    def test_win32_extended_window_styles(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=True)
        qtbot.addWidget(hud)
        hud.show()

        applied = hud.apply_win32_styles()
        assert applied is True

        import ctypes
        hwnd = int(hud.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        assert bool(style & WS_EX_LAYERED)
        assert bool(style & WS_EX_TRANSPARENT)
        assert bool(style & WS_EX_TOPMOST)
        assert bool(style & WS_EX_NOACTIVATE)
        assert bool(style & WS_EX_TOOLWINDOW)


class TestSetOfMarkRendering:
    def test_normalize_target_from_dict_and_object(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        dict_target = {
            "id": 1,
            "role": "Button",
            "label": "Submit",
            "x": 100,
            "y": 200,
            "width": 80,
            "height": 30,
        }
        norm = hud._normalize_target(dict_target)
        assert norm is not None
        assert norm.id == 1
        assert norm.role == "Button"
        assert norm.color_hex == "#00E5FF"
        assert norm.center_x == 140
        assert norm.center_y == 215

    def test_role_color_theme_mapping(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        elements = [
            {"id": 1, "role": "Button", "label": "Click Me", "x": 10, "y": 10, "width": 50, "height": 20},
            {"id": 2, "role": "Edit", "label": "Username", "x": 10, "y": 40, "width": 50, "height": 20},
            {"id": 3, "role": "OCR", "label": "Heading", "x": 10, "y": 70, "width": 50, "height": 20},
            {"id": 4, "role": "Hyperlink", "label": "Docs", "x": 10, "y": 100, "width": 50, "height": 20},
        ]
        hud.set_targets(elements)
        assert len(hud._targets) == 4
        assert hud._targets[0].color_hex == "#00E5FF"  # Cyan
        assert hud._targets[1].color_hex == "#FF007F"  # Magenta
        assert hud._targets[2].color_hex == "#F59E0B"  # Amber
        assert hud._targets[3].color_hex == "#3B82F6"  # Blue

    def test_clear_targets_and_clear_all(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        hud.set_targets([{"id": 1, "role": "Button", "label": "OK", "x": 50, "y": 50, "width": 40, "height": 20}])
        assert len(hud._targets) == 1

        hud.clear_targets()
        assert len(hud._targets) == 0

    def test_offscreen_paint_execution(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)
        hud.resize(800, 600)

        hud.set_targets([
            {"id": 1, "role": "Button", "label": "Button 1", "x": 50, "y": 50, "width": 100, "height": 40},
            {"id": 2, "role": "Edit", "label": "Input 2", "x": 200, "y": 50, "width": 100, "height": 40},
        ])

        pixmap = QPixmap(800, 600)
        hud.render(pixmap)
        assert not pixmap.isNull()


class TestTargetingReticleAndPath:
    def test_show_reticle_countdown_and_completion_signal(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        with qtbot.waitSignal(hud.sig_reticle_finished, timeout=1000) as blocker:
            hud.show_reticle(x=350, y=250, duration_ms=50, target_id=14, label="New Tab")

        assert blocker.args == [350, 250]
        assert hud._reticle_active is False

    def test_abort_reticle_cancels_immediately(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)

        with qtbot.waitSignal(hud.sig_reticle_aborted, timeout=500):
            hud.show_reticle(x=500, y=500, duration_ms=500)
            assert hud._reticle_active is True
            hud.abort_reticle()

        assert hud._reticle_active is False

    def test_bezier_path_and_reticle_paint(self, qtbot, hud_config):
        hud = GhostHUD(config=hud_config, enable_win32_styles=False)
        qtbot.addWidget(hud)
        hud.resize(1000, 800)

        hud.show_reticle(x=600, y=400, duration_ms=500, target_id=5, label="Search")
        pixmap = QPixmap(1000, 800)
        hud.render(pixmap)
        assert not pixmap.isNull()
        hud.abort_reticle()
```

---

## 8. Verification and Delivery Steps

1. **Step 1**: Implement `parasite_ai/ui/ghost_hud.py` following the exact class and method specifications in Section 5.
2. **Step 2**: Implement `tests/test_ghost_hud.py` following Section 7.
3. **Step 3**: Execute tests via `uv run pytest tests/test_ghost_hud.py` and verify 100% pass rate.
4. **Step 4**: Verify headless offscreen execution compatibility and multi-monitor geometry handling.
5. **Step 5**: Prepare handoff report in `handoff.md` and report to orchestrator.
