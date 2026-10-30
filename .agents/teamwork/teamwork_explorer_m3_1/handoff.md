# Handoff Report: Desktop Companion Dock GUI Architecture (Milestone M3)

**Author**: `teamwork_explorer_m3_1`  
**Working Directory**: `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_1\`  
**Milestone**: M3 — Desktop Companion Dock & Ghost-Hand Overlay  
**Handoff Type**: Hard (Task Complete)  

---

## 1. Observation

1. **Foundational Specifications & Requirements**:
   - `ORIGINAL_REQUEST.md`: Requirement R2 mandates an *"always-on-top desktop companion dock displaying live character speech and thoughts, state and mood indicators (WATCHING, THINKING, DRIVING, OFFLOADING, USER OVERRIDE), live perception feed, goal input, and pause/panic controls"* (lines 17-19).
   - `orchestrator/PROJECT.md`: Defines Feature 10 (Visible Companion Dock) and interface contract for `CompanionDock(QWidget)` with signals `goal_submitted(str)`, `pause_toggled(bool)`, `panic_triggered()`, and update methods (lines 18-19, 81-85).
   - `teamwork_explorer_survey_3/survey_report.md`: Specifies PyQt6 frameless always-on-top window (`WindowStaysOnTopHint | FramelessWindowHint | Tool`), default dimensions `340x540px`, bottom-right `24px` margin anchoring, high-DPI scaling, 6 operational states, dual thought/dialogue presentation, and signal definitions (lines 66-130).

2. **Existing Configuration in `parasite_ai/config.py`**:
   - `CompanionDockConfig` (lines 258-275):
     ```python
     class CompanionDockConfig(BaseModel):
         width: int = Field(default=340, ge=240, le=800)
         height: int = Field(default=540, ge=300, le=1200)
         anchor: Literal["bottom_right", "bottom_left", "top_right", "top_left", "custom"] = Field(default="bottom_right")
         margin_x: int = Field(default=24, ge=0, le=200)
         margin_y: int = Field(default=24, ge=0, le=200)
         opacity: float = Field(default=0.95, ge=0.2, le=1.0)
         always_on_top: bool = Field(default=True)
         frameless: bool = Field(default=True)
         show_thought_stream: bool = Field(default=True)
         show_perception_preview: bool = Field(default=True)
     ```
   - `UIConfig` (lines 301-306): References `CompanionDockConfig` via `dock` field.

3. **Runtime & Test Environment State**:
   - Executing `uv run pytest` executed all 321 existing test cases with 100% pass rate (`321 passed in 19.97s`).
   - `PyQt6 6.12.0` and `pytest-qt 4.5.0` are already installed and functional under Python 3.12.13 in `G:\__Docs\ParasiteAI\.venv\Scripts\python.exe`.
   - Verified PyQt6 classes (`QWidget`, `QApplication`, `QLabel`, `QPushButton`, `QLineEdit`, `QTextEdit`, `pyqtSignal`, `pyqtSlot`) load cleanly with zero runtime errors.

---

## 2. Logic Chain

1. **Window Layering & Screen Anchoring**:
   - *Premise*: The companion dock must remain visible above active applications without cluttering taskbar or Alt+Tab switcher (Observation 1, 2).
   - *Inference*: Window flags must be `Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool`. Translucent background attribute `Qt.WidgetAttribute.WA_TranslucentBackground` is necessary for smooth rounded corners (border-radius 12px) without black borders.
   - *Anchoring*: To respect the Windows taskbar, anchoring coordinates must be derived from `QGuiApplication.primaryScreen().availableGeometry()` rather than raw `geometry()`. With `bottom_right` anchor and `24px` margins:
     `x = screen_rect.x() + screen_rect.width() - dock_w - 24`
     `y = screen_rect.y() + screen_rect.height() - dock_h - 24`

2. **Repositioning & Usability**:
   - *Premise*: Stripping native window chrome prevents OS drag handles (Observation 1).
   - *Inference*: A custom drag region must be implemented on the top grip header (`mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`). To prevent accidental drag when clicking child controls, the hit-test must verify that the clicked widget is not a `QPushButton`, `QComboBox`, or interactive control. Clamping to virtual screen bounds ensures the window is never lost off-screen.

3. **Cognitive State & Mood Badge Hierarchy**:
   - *Premise*: The user must be able to glance at the dock and know whether Parasite is thinking, moving the physical cursor, paused due to human touch, or privacy-masked (Observation 1).
   - *Inference*: Define an exact 6-state palette with glowing pill badges:
     - `WATCHING`: `#10b981` (Emerald Green)
     - `THINKING`: `#f59e0b` (Amber Orange)
     - `DRIVING`: `#ef4444` (Crimson Red)
     - `USER_OVERRIDE`: `#06b6d4` (Cyan Blue)
     - `OFFLOADING`: `#8b5cf6` (Electric Purple)
     - `PROTECTED`: `#94a3b8` (Steely Grey)
     A mood pill (`[Curious]`, `[Focused]`, `[Cautious]`, etc.) supplements the state indicator.

4. **Dialogue vs. Thought Stream Separation**:
   - *Premise*: The Dual-Mind pipeline produces both character dialogue directed at the user and internal reasoning monologues (Observation 1).
   - *Inference*:
     - Character speech requires a high-contrast card (`#1e293b`) with neon state-accented borders, rich text formatting, and optional typewriter token animation.
     - Internal thoughts require a darker inset container (`#090d16`) with muted slate grey text (`#94a3b8`), italic styling, monospace font (`Consolas`), and automatic scrolling on cursor update.

5. **Action Telemetry & Perception Privacy Masking**:
   - *Premise*: 100% visible operation requires showing the pending target and thumbnail, but Window Guard requires immediate privacy blackout when password managers or admin prompts appear (Observation 1, 2).
   - *Inference*: Action telemetry displays target element ID, control type, and step progress bar. Perception preview displays downscaled thumbnail (`300x120px` max), but upon transitioning to `PROTECTED` state, replaces the thumbnail with a blackout frame displaying `🔒 SENSITIVE WINDOW ACTIVE — VISION MASKED`.

6. **Interactive Controls & Signal Safety**:
   - *Premise*: The UI runs on the main Qt thread while perception, LLM inference, and Win32 hardware hooks run on background threads. Directly calling Qt widget methods across threads causes fatal Qt crashes.
   - *Inference*: Communication must strictly use Qt signals and queued connection slots (`CompanionSignals`). Controls (Goal QLineEdit, Send button, Pause toggle, Emergency Panic button, HUD checkbox, Brain Mode dropdown) emit signals (`sig_goal_submitted`, `sig_pause_toggled`, `sig_panic_triggered`, `sig_hud_toggled`, `sig_brain_mode_changed`), while updates from background threads invoke `@pyqtSlot` handlers via queued connections.

7. **Headless Testability via `pytest-qt`**:
   - *Premise*: CI and developer test runners must verify all GUI behaviors without requiring physical display hardware (Observation 3).
   - *Inference*: Using `pytest-qt`'s `qtbot` fixture under `QT_QPA_PLATFORM=offscreen` allows complete programmatic simulation of key presses, button clicks, signal emissions (`qtbot.waitSignal`), and state transitions.

---

## 3. Caveats

1. **Multi-Monitor Boundary Snapping**: In multi-monitor setups with disparate DPI scales (e.g. 100% primary + 150% secondary), Qt automatically handles per-window scaling if `SetProcessDpiAwareness(2)` is invoked in `main.py`. The dock implementation should anchor to `primaryScreen()` by default but support dragging across multi-monitor virtual geometry.
2. **PyQt6 Event Loop in Worker Threads**: Implementers must ensure that any thread emitting updates to `CompanionDock` slots connects via Qt signals or uses `QMetaObject.invokeMethod(..., Qt.ConnectionType.QueuedConnection)` to ensure thread affinity is respected.

---

## 4. Conclusion

The technical architecture, widget hierarchy, styling specifications, signal contracts, and test plans for the Desktop Companion Dock (`parasite_ai/ui/companion_dock.py`) are fully analyzed, specified, and ready for immediate implementation.

All deliverables have been completed:
- `plan.md`: Comprehensive technical implementation plan detailing every component, geometry calculation, styling rule, Qt signal, and test specification.
- `handoff.md`: Self-contained 5-component report.

---

## 5. Verification Method

1. **Inspect Plan and Deliverables**:
   - Check `g:\__Docs\ParasiteAI\.agents\teamwork\teamwork_explorer_m3_1\plan.md` for architectural completeness across all 8 focus requirements.
2. **Verify Qt Runtime & Pytest-Qt Environment**:
   - Run: `uv run python -c "from PyQt6 import QtWidgets, QtCore; print(QtWidgets.QWidget)"`
   - Run: `uv run pytest tests/test_config.py`
3. **Downstream Worker Verification**:
   - Upon implementation of `parasite_ai/ui/companion_dock.py` and `tests/test_companion_dock.py`, workers can execute:
     `uv run pytest tests/test_companion_dock.py -v`
   - Invalidation conditions: Any test failure in signal propagation, improper window flags, offscreen positioning errors, or cross-thread GUI access exceptions.
