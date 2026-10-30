# Technical Implementation Plan: Desktop Companion Dock GUI

**Module**: `parasite_ai/ui/companion_dock.py`  
**Milestone**: M3 — Desktop Companion Dock & Ghost-Hand Overlay  
**Author**: `teamwork_explorer_m3_1`  
**Date**: 2026-10-29  

---

## 1. Architectural Overview & Scope

ParasiteAI is a 100% visible, desktop-native AI assistant operating on the physical Windows desktop with zero headless browsers and zero invisible background scrapers. The **Desktop Companion Dock** is the primary visual interface and physical anchor of the assistant on the user's screen.

### 1.1 Core Responsibilities
1. **Always-On-Top Presence**: Present on the desktop as a frameless, sleek, semi-transparent cyber-companion widget (`340x540px` default) anchored to the bottom-right corner of the primary display.
2. **State & Mood Telemetry**: Real-time visual feedback of what Parasite is doing (`WATCHING`, `THINKING`, `DRIVING`, `USER_OVERRIDE`, `OFFLOADING`, `PROTECTED`) along with personality tone (`Curious`, `Focused`, `Cautious`, etc.).
3. **Dual-Mind Expression**:
   - Spoken dialogue card directed at the user (Pass 1 Persona monologue).
   - Muted, italic internal thought stream (Pass 1/2 reasoning monologue).
4. **Action Telemetry & Live Perception Preview**:
   - Pending action metadata (target element ID, coordinates, action mode, step count).
   - Downscaled perception thumbnail preview with privacy blackout masking when sensitive windows are active.
5. **Interactive Physical Controls**:
   - Task/Goal input field with `Enter` and `Send` button triggers.
   - Hands Pause/Resume toggle button.
   - Bright red emergency Panic Abort button.
   - Screen Tags (Ghost-Hand HUD) visibility toggle.
   - Brain Mode runtime toggle (Browser Offload vs Local GGUF vs Mock).
6. **Thread-Safe Qt Signal Architecture**:
   - Decoupled Qt signals and queued connection slots bridging background engine worker threads to GUI widgets without thread race conditions.
7. **Headless Testability**:
   - 100% testable via `pytest-qt` (`qtbot`) under offscreen/headless conditions.

---

## 2. Window Properties, Geometry & Anchoring Specification

### 2.1 Window Flags & Attributes
The `CompanionDock` inherits from `PyQt6.QtWidgets.QWidget`:
```python
self.setWindowFlags(
    Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.Tool
)
self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
```

**Rationale**:
- `WindowStaysOnTopHint`: Enforces topmost z-order so the companion remains visible over open application windows (browsers, editors, terminals).
- `FramelessWindowHint`: Strips native Windows OS titlebar, borders, and buttons, allowing our custom dark cyber-aesthetic shell.
- `Tool`: Excludes the dock from the Windows taskbar and Alt+Tab application switcher, keeping the desktop uncluttered.
- `WA_TranslucentBackground`: Enables rounded window corners (`border-radius: 12px;`) and smooth dropshadow effects without black rendering artifacts.

### 2.2 Sizing & Positioning Specification
Configuration integration via `parasite_ai.config.CompanionDockConfig`:
- **Default Width**: `340px` (`config.ui.dock.width`)
- **Default Height**: `540px` (`config.ui.dock.height`)
- **Minimum Size**: `300px` x `480px`
- **Default Opacity**: `0.95` (`self.setWindowOpacity(config.ui.dock.opacity)`)
- **Anchor Offsets**: `margin_x = 24px`, `margin_y = 24px`

#### Anchoring Algorithm (`anchor_to_screen`)
```python
def anchor_to_screen(self, screen: Optional[QScreen] = None) -> None:
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    if screen is None:
        self.move(100, 100)
        return

    # Use availableGeometry() to account for Windows taskbar height!
    screen_rect = screen.availableGeometry()
    dock_w = self.width()
    dock_h = self.height()
    mx = self.config.margin_x
    my = self.config.margin_y

    anchor = self.config.anchor
    if anchor == "bottom_right":
        x = screen_rect.x() + screen_rect.width() - dock_w - mx
        y = screen_rect.y() + screen_rect.height() - dock_h - my
    elif anchor == "bottom_left":
        x = screen_rect.x() + mx
        y = screen_rect.y() + screen_rect.height() - dock_h - my
    elif anchor == "top_right":
        x = screen_rect.x() + screen_rect.width() - dock_w - mx
        y = screen_rect.y() + my
    elif anchor == "top_left":
        x = screen_rect.x() + mx
        y = screen_rect.y() + my
    else:  # "custom"
        return

    self.move(x, y)
```

### 2.3 Custom Click-and-Drag Repositioning
Since `FramelessWindowHint` removes the OS title bar, dragging is handled by custom mouse event handling on the header grip area:
- Drag trigger: Left mouse button pressed within `header_frame` (excluding interactive child buttons such as minimize or close).
- State tracking: `_is_dragging: bool`, `_drag_start_pos: QPoint`.
- Boundary Clamping: Prevents the window from being moved completely off-screen (ensures at least `60px` of header remains on screen).

```python
def mousePressEvent(self, event: QMouseEvent) -> None:
    if event.button() == Qt.MouseButton.LeftButton:
        # Check if click is in header area and not on interactive buttons
        if self._header_grip.geometry().contains(event.pos()):
            child = self.childAt(event.pos())
            if child is None or not isinstance(child, (QPushButton, QComboBox, QCheckBox)):
                self._is_dragging = True
                self._drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return
    super().mousePressEvent(event)

def mouseMoveEvent(self, event: QMouseEvent) -> None:
    if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
        target_pos = event.globalPosition().toPoint() - self._drag_start_pos
        self.move(self._clamp_to_virtual_desktop(target_pos))
        event.accept()
        return
    super().mouseMoveEvent(event)

def mouseReleaseEvent(self, event: QMouseEvent) -> None:
    self._is_dragging = False
    super().mouseReleaseEvent(event)
```

---

## 3. Visual States, Mood Indicators & Color Architecture

### 3.1 State Machine & Accent Palette
The Companion Dock visually reflects the current cognitive/physical state of ParasiteAI across 6 distinct operational states:

| State | Hex Accent | RGB / Alpha | Semantic Meaning |
|---|---|---|---|
| `WATCHING` | `#10B981` | `rgba(16, 185, 129, 0.2)` | Idle, perceiving screen, awaiting user goal or desktop changes |
| `THINKING` | `#F59E0B` | `rgba(245, 158, 11, 0.2)` | Cognitive reasoning / LLM generation in progress |
| `DRIVING` | `#EF4444` | `rgba(239, 68, 68, 0.2)` | Actively moving physical mouse or executing Unicode keystrokes |
| `USER_OVERRIDE`| `#06B6D4` | `rgba(6, 182, 212, 0.2)` | Interrupted by user physical hardware touch (<2ms); hands yielded |
| `OFFLOADING` | `#8B5CF6` | `rgba(139, 92, 246, 0.2)` | Visibly driving Chrome browser to offload frontier reasoning |
| `PROTECTED` | `#94A3B8` | `rgba(148, 163, 184, 0.2)` | Sensitive window (Bitwarden, KeePass, etc.) active; screen masked |

### 3.2 State Pill & Mood Badge Styling
```python
STATE_CONFIG = {
    "WATCHING": {"color": "#10b981", "bg": "rgba(16, 185, 129, 0.15)", "label": "● WATCHING"},
    "THINKING": {"color": "#f59e0b", "bg": "rgba(245, 158, 11, 0.15)", "label": "● THINKING"},
    "DRIVING": {"color": "#ef4444", "bg": "rgba(239, 68, 68, 0.15)", "label": "● DRIVING"},
    "USER_OVERRIDE": {"color": "#06b6d4", "bg": "rgba(6, 182, 212, 0.15)", "label": "● OVERRIDE"},
    "OFFLOADING": {"color": "#8b5cf6", "bg": "rgba(139, 92, 246, 0.15)", "label": "● OFFLOADING"},
    "PROTECTED": {"color": "#94a3b8", "bg": "rgba(148, 163, 184, 0.15)", "label": "🔒 PROTECTED"},
}
```

- **Pill Badge**: `QLabel` with border radius `10px`, padding `3px 8px`, bold font `9pt`.
- **Mood Pill**: `QLabel` showing personality disposition (`[Curious]`, `[Focused]`, `[Cautious]`, `[Amused]`, `[Panic-Averted]`).
- **Dynamic Glow Effect**: Outer card border highlights smoothly with the active state's accent color (`border: 1px solid {accent_color};`).

---

## 4. Widget Components & UI Hierarchy

```
CompanionDock (QWidget)
└── Root Layout (QVBoxLayout: margins 8, 8, 8, 8)
    └── MainCard (QFrame: #MainCard, border-radius 12px, bg #0f172a)
        └── Card Layout (QVBoxLayout: margins 12, 12, 12, 12, spacing 8)
            ├── Header Grip Frame (QHBoxLayout)
            │   ├── Avatar Icon (QLabel: 24x24 cyber badge)
            │   ├── Title Label ("PARASITE" - 10pt bold)
            │   ├── State Pill (QLabel: "● WATCHING")
            │   ├── Mood Pill (QLabel: "[Curious]")
            │   ├── Stretch
            │   └── Minimize / Quick Panic Buttons
            ├── Character Speech Bubble (QFrame: #SpeechCard)
            │   └── QVBoxLayout
            │       ├── Sender Label ("Parasite" in cyan accent)
            │       └── Dialogue Text (QLabel: wordWrap=True, font 10pt)
            ├── Internal Thought Stream (QFrame: #ThoughtCard)
            │   └── QVBoxLayout
            │       ├── Thought Header ("💭 Internal Monologue")
            │       └── Thought Area (QPlainTextEdit / QTextEdit: readOnly, italic muted #94a3b8)
            ├── Action Telemetry Feed (QFrame: #TelemetryCard)
            │   └── QVBoxLayout
            │       ├── Target & Action Line ("Target: [#14] Button 'New Tab' | Mode: CLICK")
            │       └── Step Progress Line ("Step 3/10" + mini QProgressBar)
            ├── Live Perception Preview (QFrame: #PerceptionCard)
            │   └── QVBoxLayout
            │       ├── Thumbnail Viewport (QLabel: scaled pixmap, max-height 120px)
            │       └── Grounding Summary Badge ("Grounding: 34 UIA | 6 OCR")
            └── Interactive Controls Section (QVBoxLayout)
                ├── Goal Input Row (QHBoxLayout)
                │   ├── Goal LineEdit (QLineEdit: placeholder "Give Parasite a task...")
                │   └── Send Button (QPushButton: "Send")
                ├── Primary Action Controls Row (QHBoxLayout)
                │   ├── Pause / Resume Hands Toggle (QPushButton: "⏸ Pause Hands")
                │   └── Emergency Panic Button (QPushButton: "⚠ PANIC ABORT")
                └── Secondary Utility Controls Row (QHBoxLayout)
                    ├── HUD Tags Checkbox (QCheckBox: "Show HUD Tags [#ID]")
                    └── Brain Mode Dropdown (QComboBox: Browser Offload / Local GGUF / Mock)
```

### 4.1 Character Speech Bubble (Dialogue Card)
- **Role**: Primary communication channel from Parasite to user (Pass 1 Persona monologue).
- **Styling**:
  ```css
  #SpeechCard {
      background-color: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 8px;
  }
  ```
- **Capabilities**:
  - `set_speech(text: str, stream: bool = False)`
  - Streaming Mode: Uses internal `QTimer` (`20ms` interval) to typewriter-animate tokens into view if `stream=True`.
  - Supports Markdown / Rich Text formatting (bold, links, code tags).

### 4.2 Internal Thought Stream
- **Role**: Displays un-lobotomized thinking process (Pass 1 & Pass 2 internal thoughts).
- **Styling**:
  ```css
  #ThoughtCard {
      background-color: #090d16;
      border: 1px solid #1e293b;
      border-radius: 6px;
      padding: 6px;
  }
  #ThoughtText {
      color: #94a3b8;
      font-style: italic;
      font-family: 'Consolas', 'Segoe UI', monospace;
      font-size: 9pt;
      background: transparent;
      border: none;
  }
  ```
- **Auto-scroll**: `self.thought_text.ensureCursorVisible()` keeps the newest thoughts in view.
- **Config Toggle**: Visible only when `config.ui.dock.show_thought_stream is True`.

### 4.3 Action Telemetry Feed
- **Role**: Immediate transparency into what action Parasite has selected and is executing.
- **Displays**:
  - `Target`: Element ID, control type, label, coordinates (e.g. `[#14] Button "New Tab" at (240, 18)`).
  - `Action`: Mode (`CLICK`, `TYPE`, `HOTKEY`, `SCROLL`, `WAIT`), reticle preview status (`300ms preview`).
  - `Step Progress`: Step count (`Step 3/10`) and compact `QProgressBar` (height `4px`, colored with accent).

### 4.4 Live Perception Preview Thumbnail
- **Role**: Downscaled view of the captured desktop scene or active focus area.
- **Styling**: Max dimensions `300x120px`, aspect ratio preserved via `Qt.AspectRatioMode.KeepAspectRatio` and `Qt.TransformationMode.SmoothTransformation`.
- **Grounding Badge**: Overlaid or adjacent label showing e.g. `Grounding: 34 UIA | 6 OCR`.
- **Privacy Blackout Mask**:
  - When state is set to `PROTECTED` (or `set_perception_masked(True)`), the preview thumbnail immediately blanks out to a solid black rectangle displaying:
    `🔒 SENSITIVE WINDOW ACTIVE — VISION MASKED`
  - Prevents passwords or sensitive user credentials from ever being rendered on the dock thumbnail.
- **Config Toggle**: Visible only when `config.ui.dock.show_perception_preview is True`.

### 4.5 Interactive Controls Subsystem
1. **Goal Input**:
   - `QLineEdit`: dark themed, clear button enabled, placeholder `"Give Parasite a task..."`.
   - Triggers: User presses `Enter` (`returnPressed`) OR clicks `Send` button.
   - Behavior:
     - Extracts text, trims whitespace.
     - If non-empty: clears input field, emits `sig_goal_submitted(goal_text)`.
2. **Pause / Resume Hands Toggle**:
   - `QPushButton`: toggles between two visual states:
     - Active Hands: Text `"⏸ Pause Hands"`, style amber accent.
     - Paused Hands: Text `"▶ Resume Hands"`, style emerald accent.
   - Emits: `sig_pause_toggled(is_paused: bool)`.
3. **Emergency Panic Button**:
   - `QPushButton`: Bright crimson red (`#ef4444`), bold white text: `"⚠ PANIC ABORT"`.
   - Single click triggers immediate abort of all synthetic movement and resets execution.
   - Emits: `sig_panic_triggered()`.
4. **HUD Tags Checkbox**:
   - `QCheckBox`: `"Show HUD Tags [#ID]"`, checked by default.
   - Emits: `sig_hud_toggled(show_hud: bool)`.
5. **Brain Mode Dropdown**:
   - `QComboBox`:
     - `"Browser Offload (Zero-VRAM)"` (value: `"browser_offload"`)
     - `"Local GGUF (GPU)"` (value: `"local_llm"`)
     - `"Mock / Test Mode"` (value: `"mock"`)
   - Emits: `sig_brain_mode_changed(mode: str)`.

---

## 5. Qt Signal Architecture & Cross-Thread Safety

### 5.1 Signal Definitions (`CompanionSignals`)
All communication from the UI to engine components and from engine components to UI is governed by Qt Signals:

```python
class CompanionSignals(QObject):
    # Status & Expression
    sig_status_changed = pyqtSignal(str, str)         # (state: str, mood: str)
    sig_thought_updated = pyqtSignal(str)             # (thought_text: str)
    sig_speech_updated = pyqtSignal(str)              # (speech_text: str)
    sig_telemetry_updated = pyqtSignal(str)           # (telemetry_text: str)
    sig_perception_updated = pyqtSignal(object)        # (pixmap_or_image: QPixmap | QImage | np.ndarray)

    # User Interactive Controls
    sig_goal_submitted = pyqtSignal(str)              # (goal_text: str)
    sig_pause_toggled = pyqtSignal(bool)              # (is_paused: bool)
    sig_panic_triggered = pyqtSignal()                # ()
    sig_hud_toggled = pyqtSignal(bool)                # (show_hud: bool)
    sig_brain_mode_changed = pyqtSignal(str)          # (mode: str)
```

### 5.2 Thread-Safe Invocation Protocol
Background worker threads (Perception loop, Brain inference, Hardware hook threads) MUST NOT mutate Qt widgets directly. Instead, the `CompanionDock` provides thread-safe Qt slots that accept Queued Connections:

```python
@pyqtSlot(str, str)
def update_status(self, state: str, mood: str = "Curious") -> None:
    ...

@pyqtSlot(str)
def update_speech(self, text: str) -> None:
    ...

@pyqtSlot(str)
def update_thought(self, text: str) -> None:
    ...

@pyqtSlot(str)
def update_telemetry(self, text: str) -> None:
    ...

@pyqtSlot(object)
def update_perception_preview(self, frame_data: Any) -> None:
    ...

@pyqtSlot(bool)
def set_hands_paused(self, is_paused: bool) -> None:
    ...
```

The dock instance exposes `self.signals = CompanionSignals()`, and exposes class-level forwarder signals or connects its internal buttons directly to `self.signals`.

---

## 6. Comprehensive Test Specifications (`pytest-qt` / `qtbot`)

All tests must run cleanly in both desktop and offscreen (`QT_QPA_PLATFORM=offscreen`) environments without hanging.

### 6.1 Test Matrix

| Test Function | Verification Target | Assertion Criteria |
|---|---|---|
| `test_dock_initialization_defaults` | Default instantiation with `CompanionDockConfig` | Window flags include `WindowStaysOnTopHint`, `FramelessWindowHint`, `Tool`; size matches config (340x540); opacity 0.95. |
| `test_dock_screen_anchoring` | Position calculations for all 4 corners | Verify dock moves to correct `(x, y)` based on `availableGeometry()` and margins for `bottom_right`, `bottom_left`, `top_right`, `top_left`. |
| `test_dock_state_transitions` | All 6 visual states (`WATCHING`, `THINKING`, `DRIVING`, `USER_OVERRIDE`, `OFFLOADING`, `PROTECTED`) | Calling `update_status(state, mood)` updates label text, accent colors, and emits `sig_status_changed`. |
| `test_dock_speech_updates` | Speech bubble rendering | Calling `update_speech("Hello World")` updates dialogue label; verifies rich text and typewriter streaming. |
| `test_dock_thought_stream` | Thought stream rendering | Calling `update_thought("Thinking...")` appends text, scrolls cursor, updates widget. |
| `test_dock_telemetry_feed` | Telemetry text and step progress | `update_telemetry(...)` updates labels; progress bar updates value. |
| `test_dock_perception_preview_and_masking` | Perception thumbnail display and sensitive window masking | Synthetic `QPixmap` renders on thumbnail; setting state to `PROTECTED` renders privacy mask. |
| `test_goal_input_return_key` | Submitting goal via Enter key | `qtbot.keyClicks(dock.goal_input, "Open Chrome")` + `qtbot.keyClick(dock.goal_input, Qt.Key.Key_Return)` emits `sig_goal_submitted` with `"Open Chrome"` and clears line edit. |
| `test_goal_input_send_button` | Submitting goal via Send button | `qtbot.keyClicks(dock.goal_input, "Take screenshot")` + `qtbot.mouseClick(dock.btn_send, Qt.MouseButton.LeftButton)` emits `sig_goal_submitted` with `"Take screenshot"`. |
| `test_pause_resume_toggle` | Pause/Resume button toggling | First click emits `sig_pause_toggled(True)` and updates button label; second click emits `sig_pause_toggled(False)`. |
| `test_panic_button_signal` | Emergency Panic button | Clicking Panic button immediately emits `sig_panic_triggered()`. |
| `test_hud_checkbox_toggle` | Screen tags HUD toggle | Toggling checkbox emits `sig_hud_toggled(bool)`. |
| `test_brain_mode_dropdown` | Brain mode selection | Selecting item in combo box emits `sig_brain_mode_changed` with corresponding mode identifier. |
| `test_mouse_drag_repositioning` | Header drag simulation | Simulating `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent` updates dock position within valid screen bounds. |

---

## 7. Implementation Roadmap & Concrete Code Layout

### Target File: `parasite_ai/ui/companion_dock.py`

```python
"""
ParasiteAI - Desktop Companion Dock Widget (PyQt6).
Provides the 100% visible, always-on-top companion GUI displaying character
state, mood, speech monologue, internal thoughts, action telemetry, perception
preview, and interactive user controls.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from PyQt6.QtCore import (
    QObject,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QImage,
    QMouseEvent,
    QPainter,
    QPixmap,
    QScreen,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from parasite_ai.config import CompanionDockConfig, AppConfig

logger = logging.getLogger(__name__)

# [Implementation details as structured above]
```

### Key Milestones for Workers:
1. **Phase 1**: Widget skeleton, stylesheet constants, window flags, drop shadow, and anchoring calculations.
2. **Phase 2**: Header bar, Avatar, 6-state LED pill badges and mood indicator.
3. **Phase 3**: Character speech bubble with streaming typewriter effect and internal thought stream.
4. **Phase 4**: Action telemetry feed and perception thumbnail with sensitive window privacy masking.
5. **Phase 5**: Interactive controls (goal input, pause/resume, emergency panic, HUD toggle, brain mode).
6. **Phase 6**: Qt signal wiring, cross-thread slot bridges, and drag-and-drop repositioning logic.
7. **Phase 7**: Comprehensive `pytest-qt` automated test suite in `tests/test_companion_dock.py`.
