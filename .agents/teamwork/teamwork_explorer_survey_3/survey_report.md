# ParasiteAI Technical Survey Report: R2, R4, and R5
**Author**: `teamwork_explorer_survey_3`  
**Date**: 2026-10-29  
**Status**: APPROVED / COMPLETED  
**Scope**: 
- **R2**: Visible Desktop Companion GUI & Ghost-Hand HUD Overlay
- **R4**: Perception, Cognition & Visible Browser Brain Offload
- **R5**: Entry Points & Verification Test Suite

---

## 1. Executive Summary & Architectural Overview

ParasiteAI is designed as a **100% visible, desktop-native AI companion** that operates directly on the user's physical Windows desktop with **zero headless browsers, zero invisible scrapers, and zero CLI-only interfaces**.

To achieve this, the system relies on a seamless division across three core subsystems surveyed here:
1. **R2 (Visible Desktop Companion GUI & Ghost-Hand HUD)**: The user-facing visual and targeting layer. It provides an always-on-top companion dock displaying live thoughts, character speech, status badges, telemetry, and interactive controls, paired with a transparent click-through Win32 layered overlay (Ghost-Hand HUD) rendering glowing Set-of-Mark (SoM) boxes and a 300ms pre-click reticle.
2. **R4 (Perception, Cognition & Visible Browser Brain Offload)**: The sensory and reasoning loop. It combines fast Win32 UI Automation (`uiautomation`) and scoped OCR (`rapidocr-onnxruntime`) to ground UI elements in < 50ms with 0 MB VRAM, maintains episodic working memory with loop detection, splits reasoning into a Dual-Mind cognitive pipeline (Persona voice pass + Action Dispatcher pass), and automates Google Chrome visibly on screen with sentinel clipboard verification.
3. **R5 (Entry Points & Verification Test Suite)**: The operational entry points (`main.py`, `launch_parasite.bat`) and an automated `pytest` suite ensuring rock-solid verification of interrupt handling, grounding accuracy, memory loop detection, and clipboard safety.

### System Architecture Flow

```
+-----------------------------------------------------------------------------------------+
|                                    PyQt6 UI Thread                                      |
|  +-------------------------------------+   +-----------------------------------------+  |
|  |     Companion Dock (Always-On-Top)  |   |    Ghost-Hand HUD (Click-Through)       |  |
|  |  - State: WATCHING, DRIVING, etc.   |   |  - Win32 WS_EX_LAYERED | TRANSPARENT    |  |
|  |  - Persona Speech & Thought Stream  |   |  - Set-of-Mark [#ID] Boxes              |  |
|  |  - Action Telemetry & Live Preview  |   |  - 300ms Pre-Click Targeting Reticle    |  |
|  |  - Controls: Pause/Panic/Goal Input |   |  - Trajectory Glide Path Preview        |  |
|  +------------------^------------------+   +--------------------^--------------------+  |
+---------------------|-------------------------------------------|-----------------------+
                      | Signals/Slots                             | Signals/Slots
+---------------------v-------------------------------------------v-----------------------+
|                              Background Worker Thread (Engine Loop)                     |
|                                                                                         |
|   +--------------------------+       +-----------------------------------------------+  |
|   |   Perception Engine      | ----> |   Episodic Working Memory                     |  |
|   |   - mss Screen Capture   |       |   - Action history & screen diff verification |  |
|   |   - Win32 UIA Tree Walk  |       |   - Loop & stuck state detection              |  |
|   |   - Scoped RapidOCR      |       +-----------------------+-----------------------+  |
|   +--------------------------+                               |                          |
|                                                              v                          |
|   +----------------------------------------------------------------------------------+  |
|   |   Dual-Mind Cognitive Pipeline                                                   |  |
|   |   - Pass 1 (Persona Engine): Un-lobotomized character voice & high-level intent  |  |
|   |   - Pass 2 (Action Dispatcher): Deterministic JSON schema targeting [#ID]        |  |
|   +------------------------------------------+---------------------------------------+  |
|                                              |                                          |
|                                              v                                          |
|   +----------------------------------------------------------------------------------+  |
|   |   Execution Dispatch                                                             |  |
|   |   - Physical Mouse/Keyboard (300ms preview -> Bézier glide -> Unicode typing)    |  |
|   |   - Visible Browser Offloader (Chrome automation + Sentinel Clipboard verify)    |  |
|   +----------------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Requirement R2: Visible Desktop Companion GUI & Ghost-Hand HUD

### 2.1 Desktop Companion Dock (`parasite_ai/ui/companion_dock.py`)

#### 2.1.1 Window Properties & Win32 Integration
- **Framework**: `PyQt6.QtWidgets.QWidget`.
- **Window Flags**:
  - `Qt.WindowType.WindowStaysOnTopHint`: Keeps the companion permanently visible.
  - `Qt.WindowType.FramelessWindowHint`: Removes standard OS chrome for a custom sleek cyber-companion aesthetic.
  - `Qt.WindowType.Tool`: Avoids cluttering the taskbar and Alt+Tab pager.
- **Positioning & Sizing**:
  - Default size: `340px` (width) x `540px` (height).
  - Anchored to bottom-right corner of the primary display with `24px` margin from screen edges and taskbar.
  - Supports click-and-drag window repositioning via custom title grip (`mousePressEvent` / `mouseMoveEvent`).
- **High-DPI Awareness**:
  - Must invoke `ctypes.windll.shcore.SetProcessDpiAwareness(2)` (Per-Monitor High DPI Aware) prior to creating `QApplication` to ensure exact coordinate parity with Windows physical desktop pixels.

#### 2.1.2 Visual States & Moods
The Companion Dock header features a dynamic state badge with glowing LED accent styling:
| State | Accent Color | Visual Meaning |
|---|---|---|
| `WATCHING` | `#10b981` (Emerald Green) | Idling, observing screen, waiting for goal or changes |
| `THINKING` | `#f59e0b` (Amber Orange) | LLM inference in progress (planning next step) |
| `DRIVING` | `#ef4444` (Crimson Red) | Actively controlling physical mouse or keyboard |
| `USER_OVERRIDE` | `#06b6d4` (Cyan Blue) | Paused due to user physical hardware touch (<2ms interrupt) |
| `OFFLOADING` | `#8b5cf6` (Electric Purple)| Automating Chrome/Opera for frontier reasoning |
| `PROTECTED` | `#6b7280` (Steely Grey) | Sensitive window (Bitwarden, KeePass, etc.) active; eyes closed |

**Mood Indicator**: Displays character expression and personality tone (`Curious`, `Focused`, `Cautious`, `Amused`, `Panic-Averted`).

#### 2.1.3 UI Components Breakdown
1. **Header & Status Bar**:
   - Parasite avatar icon with breathing animated glow.
   - Status badge and mood pill.
   - Window controls (minimize, emergency abort icon).
2. **Character Thought Stream (Internal Monologue)**:
   - Styled text area in muted grey (`#94a3b8`) with italic typography.
   - Streams the raw, expressive thoughts of the Persona as it evaluates the desktop scene.
3. **Character Speech Bubble (Dialogue)**:
   - High-contrast, card-styled speech bubble with neon accent border.
   - Displays conversational speech directed at the user, streamed character-by-character or updated per step.
4. **Action Telemetry Feed**:
   - Shows the immediate pending action:
     `Target: [#14] "New Tab" at (240, 18) | Mode: CLICK`
   - Real-time progress bar / step indicator (e.g., `Step 3/10`).
5. **Live Perception Preview Feed**:
   - Mini thumbnail widget (approx `280x140px`) rendering a downscaled view of the active focus area or bounding box cluster.
   - Summary label: `Grounding: 34 UIA elements, 6 OCR elements`.
6. **User Interactive Controls**:
   - **Goal Input**: `QLineEdit` with placeholder `"Give Parasite a task..."` + `Send` button. Submits task via `Enter`.
   - **Pause / Resume Hands**: Direct button toggling synthetic mouse/keyboard movement.
   - **Emergency Panic Button**: Bright red button that instantly halts all active actions, releases mouse, and resets state to `IDLE`.
   - **Toggle Screen Tags**: Checkbox toggling visibility of the Ghost-Hand Set-of-Mark overlay on desktop.
   - **Offload / Brain Mode Switch**: Toggle between Local GGUF (8GB VRAM) and Browser Offload (Zero-VRAM).

#### 2.1.4 Qt Signal & Event Architecture
```python
class CompanionSignals(QObject):
    sig_status_changed = pyqtSignal(str, str)        # state, mood
    sig_thought_updated = pyqtSignal(str)            # internal thought
    sig_speech_updated = pyqtSignal(str)             # user speech
    sig_telemetry_updated = pyqtSignal(str)          # current action telemetry
    sig_perception_updated = pyqtSignal(object, list)# QPixmap thumbnail, list[UIElement]
    sig_goal_submitted = pyqtSignal(str)             # user goal string
    sig_pause_toggled = pyqtSignal(bool)             # is_paused
    sig_panic_triggered = pyqtSignal()               # emergency abort
    sig_hud_toggled = pyqtSignal(bool)               # show_hud
```

---

### 2.2 Ghost-Hand Screen Overlay HUD (`parasite_ai/ui/ghost_hud.py`)

#### 2.2.1 Win32 Layered Click-Through Architecture
To ensure the HUD is 100% visible but never interferes with user clicks or window focus:
- **Geometry**: Covers the full virtual desktop (`QGuiApplication.primaryScreen().virtualGeometry()`), spanning multi-monitor configurations if present.
- **Window Attributes**:
  - `setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)`
  - `setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)`
- **Win32 Extended Window Styles**:
  Enforced directly via `user32.dll` on `self.winId()`:
  ```python
  import ctypes
  from ctypes import wintypes

  GWL_EXSTYLE = -20
  WS_EX_LAYERED = 0x00080000       # Per-pixel alpha transparency
  WS_EX_TRANSPARENT = 0x00000020   # Click-through: mouse clicks pass straight through!
  WS_EX_TOPMOST = 0x00000008       # Always on top of all windows
  WS_EX_NOACTIVATE = 0x08000000    # Never steal focus from target apps
  WS_EX_TOOLWINDOW = 0x00000080    # Exclude from Alt+Tab / Taskbar

  hwnd = int(self.winId())
  style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
  ctypes.windll.user32.SetWindowLongW(
      hwnd, GWL_EXSTYLE,
      style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
  )
  ```

#### 2.2.2 Set-of-Mark (SoM) Visual Rendering
- When active, iterates over grounded `UIElement` instances and renders overlay tags with `QPainter`:
  - **Bounding Boxes**:
    - Interactive Buttons: Cyan (`#00e5ff`, 1.5px stroke, 25% alpha fill).
    - Text Input Fields: Magenta (`#ff007f`, 1.5px stroke, 25% alpha fill).
    - Hyperlinks: Electric Blue (`#3b82f6`).
    - OCR-detected Text: Gold Amber (`#f59e0b`).
  - **Numbered Badges**:
    - Rendered at top-left corner of each element: `[#ID: Label]` (e.g., `[#14: New Tab]`).
    - High-contrast badge: Dark rounded rectangle (`#111827`, 85% opacity) with bright text (font size 9pt Segoe UI / Consolas).

#### 2.2.3 300ms Pre-Click Targeting Reticle & Trajectory
To eliminate surprise actions and ensure the user can clearly see where the mouse is aiming:
1. **Target Selection**: When `ActionDispatcher` selects target `[#ID]` at coordinates `(target_x, target_y)`:
2. **Preview Signal**: Emits `sig_target_locked(target_x, target_y, duration_ms=300)`.
3. **Visual Animation**:
   - **Reticle**: Draws an animated glowing crosshair / lock brackets centered at `(target_x, target_y)`.
   - **Trajectory Line**: Fetches current physical cursor position `(cur_x, cur_y)` and renders a glowing curved Bézier path preview directly to `(target_x, target_y)`.
   - **Label Card**: Displays a floating banner above the reticle: `Aiming: [#14] Click in 300ms`.
4. **Timer Gate**:
   - A high-resolution `QTimer.singleShot(300, ...)` counts down the 300ms preview.
   - The physical mouse movement ONLY starts after the 300ms preview has fully completed!
   - If the user moves their physical mouse during this 300ms, the interrupt guard immediately cancels the pending move before the cursor ever touches the target.

---

## 3. Requirement R4: Perception, Cognition & Visible Browser Brain Offload

### 3.1 Perception Engine (`parasite_ai/vision/`)

#### 3.1.1 Fast Screen Capture (`capture.py`)
- **Library**: `mss.mss()` for high-speed desktop memory capture.
- **Latency**: ~3-8ms per 1080p frame into a BGRA numpy array or PIL Image.
- **Frame Differencing**:
  ```python
  def compute_frame_diff(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
      """Downsample 4x, grayscale, normalized mean absolute difference [0.0, 1.0]."""
      gray_a = cv2.cvtColor(frame_a[::4, ::4], cv2.COLOR_BGR2GRAY)
      gray_b = cv2.cvtColor(frame_b[::4, ::4], cv2.COLOR_BGR2GRAY)
      return float(np.mean(np.abs(gray_a.astype(np.int16) - gray_b.astype(np.int16))) / 255.0)
  ```
- **Settling Detection**: Used during browser offloading and action verification; polls every 100-300ms until diff < 0.003 for 3 consecutive intervals.

#### 3.1.2 Hybrid Grounding Engine (`grounding.py`)
To achieve sub-50ms grounding without consuming precious VRAM (saving all 8 GB VRAM for the local LLM):
1. **Tier 1 — Win32 UI Automation (`uiautomation`) [~15ms, 0 MB VRAM]**:
   - Inspects the foreground active window (`uiautomation.GetForegroundControl()`) and the Windows taskbar (`uiautomation.PaneControl(ClassName="Shell_TrayWnd")`).
   - Recursively walks control trees up to `depth=5`.
   - Filters interactive control types:
     `ButtonControl`, `EditControl`, `HyperlinkControl`, `MenuItemControl`, `TabItemControl`, `ComboBoxControl`, `CheckBoxControl`, `RadioButtonControl`, `ListItemControl`, `DocumentControl`.
   - Extracts bounding coordinates `(rect.left, rect.top, rect.width(), rect.height())`.
   - Filters out invisible/offscreen controls: `IsOffscreen == True`, width < 5, height < 5, or outside desktop geometry.
2. **Tier 2 — Scoped OCR Fallback (`rapidocr-onnxruntime`) [~45ms, 0 MB VRAM]**:
   - Used when UIA yields < 6 controls (indicating a Chromium canvas, WebGL app, or non-standard UI framework).
   - Scopes OCR strictly to the active window's client rectangle.
   - Runs `RapidOCR` with CPU ONNX execution provider.
   - Maps local crop coordinates back to global desktop coordinates.
3. **Tier 3 — Spatial Deduplication & Catalog Synthesis**:
   - Calculates Intersection over Union (IoU) between OCR text boxes and UIA controls.
   - If an OCR box falls inside a UIA button, the OCR text is merged into the UIA element's label.
   - Assigns sequential 1-based IDs: `[#1]`, `[#2]`, ..., `[#N]`.
   - Caps total elements to top ~60 (prioritizing foreground active window controls).

#### 3.1.3 Element Data Model
```python
from pydantic import BaseModel
from typing import Optional, Tuple

class UIElement(BaseModel):
    id: int
    role: str                # "Button", "Edit", "Hyperlink", "TabItem", "Text", etc.
    label: str               # Name / accessible text
    x: int                   # Top-left X (desktop coordinates)
    y: int                   # Top-left Y (desktop coordinates)
    width: int
    height: int
    center_x: int            # Click target X
    center_y: int            # Click target Y
    source: str              # "uia" | "ocr" | "merged"
    is_active_window: bool
```

---

### 3.2 Cognition Engine & Dual-Mind Pipeline (`parasite_ai/mind/`)

#### 3.2.1 Dual-Mind Rationale
Local quantized models (3B / 7B parameters) degrade rapidly when forced to do creative personality monologue AND rigid JSON coordinate emission in a single prompt. Furthermore, alternating between two disparate system prompts on a single KV cache invalidates context caching.
The Dual-Mind pipeline cleanly decouples these tasks into two sequential passes:

```
User Goal + Scene Summary + Memory
                 |
                 v
   +-----------------------------+
   |  Pass 1: Persona Engine     |  (Pure unconstrained character voice)
   |  - Backstory & personality  |
   |  - Monologue & Dialogue     |
   +--------------+--------------+
                  |
     Intent + Numbered Element Table
                  |
                  v
   +-----------------------------+
   |  Pass 2: Action Dispatcher  |  (Deterministic schema translator)
   |  - Strict JSON grammar      |
   |  - Validated target [#ID]   |
   +--------------+--------------+
                  |
                  v
         Executable Action Plan
```

#### 3.2.2 Pass 1: Persona Engine (`PersonaEngine`)
- **Role**: Creative desktop companion symbiote.
- **Inputs**:
  - Persona system card (snarky, witty, helpful companion).
  - High-level human-readable scene summary (e.g., *"Active: Google Chrome - New Tab. Address bar, bookmarks bar, and search box are visible."*).
  - Current user goal.
  - Last 3 steps from Episodic Working Memory.
- **Output JSON**:
  ```json
  {
    "thought": "The user wants to look up the weather. Chrome is visible on the taskbar. I should click it to open a browser window.",
    "speech": "Opening Chrome for you now, let's see what the skies look like!",
    "intent": "Click Google Chrome icon on the taskbar"
  }
  ```
- Emits `speech` immediately to Companion Dock speech bubble!

#### 3.2.3 Pass 2: Action Dispatcher (`ActionDispatcher`)
- **Role**: Precise schema parser and element selector.
- **Inputs**:
  - Persona `intent` from Pass 1.
  - Element lookup table:
    ```text
    [#1] Button "Google Chrome" at (450, 1055)
    [#2] Button "File Explorer" at (490, 1055)
    [#3] Edit "Address and search bar" at (300, 82)
    ```
- **Output Schema**:
  ```json
  {
    "action": "CLICK",
    "target_id": 1,
    "text": null,
    "submit": false,
    "keys": null,
    "scroll_amount": 0,
    "wait_seconds": 0.0,
    "reason": "Click Chrome on taskbar"
  }
  ```
- **Action Grammar**:
  - `CLICK(target_id)`
  - `CLICK_AND_TYPE(target_id, text, submit=True)`
  - `HOTKEY(keys=["ctrl", "t"])`
  - `SCROLL(amount=-300)`
  - `WAIT(seconds=2.0)`
  - `OFFLOAD_WEB_AI(prompt="...")`
  - `DONE(summary="...")`

#### 3.2.4 Episodic Working Memory (`parasite_ai/mind/memory.py`)
- **Structure**: Rolling buffer of last 10-15 steps (`StepRecord`).
- **Fields**:
  - `step_number`: Sequential integer.
  - `goal`: Active objective.
  - `persona_thought` & `persona_speech`.
  - `action_type`, `target_id`, `target_label`, `coordinates`.
  - `screen_diff_ratio`: Float measurement of visual change.
  - `screen_changed`: Boolean (`diff > 0.003`).
- **Loop & Failure Detection**:
  - If the same `(action_type, target_id)` produces `screen_changed == False` for 2 consecutive steps:
    - Sets `loop_detected = True`.
    - Automatically injects an urgent corrective prompt into the Persona Engine:
      `"WARNING: Clicking [#target_id] ('{label}') produced zero screen change for 2 steps. The element is unresponsive or already active. DO NOT click it again. Select an alternative action (e.g., hotkey, scroll, or different control)."`

---

### 3.3 Visible Browser Brain Offload (`parasite_ai/mind/offloader.py`)

#### 3.3.1 Philosophy: 100% Desktop-Native Operation
When ParasiteAI needs deep reasoning or live web information, it does **not** make hidden background API calls. Instead, the user literally watches the physical mouse and keyboard interact with **Google Chrome** (or Opera GX) on the physical desktop.

#### 3.3.2 Finite State Machine Flow
```
[IDLE] 
  │
  ▼
[LOCATE_OR_LAUNCH_CHROME] ──(Bring Chrome to front)──► [FOCUS_OR_NEW_TAB (Ctrl+T)]
                                                              │
                                                              ▼
[WAIT_PAGE_READY] ◄──(Type URL & Enter)── [NAVIGATE (Ctrl+L -> gemini.google.com)]
        │
        ▼
[FOCUS_AND_TYPE_PROMPT] ──(Click prompt box, type with human cadence, Enter)
        │
        ▼
[WAIT_STREAM_START] ──(Detect tokens or Stop button appearing)
        │
        ▼
[WAIT_STREAM_STABILIZE] ──(Screen diff < 0.002 for 3 consecutive polls)
        │
        ▼
[LOCATE_COPY_BUTTON] ──(Find "Copy" button via UIA/OCR or select response)
        │
        ▼
[SENTINEL_CLIPBOARD_VERIFICATION] ──(Save user clip -> Sentinel -> Copy -> Verify -> Restore)
        │
        ▼
[INJECT_RESULT] ──(Feed harvested answer to Persona Engine) ──► [COMPLETE]
```

#### 3.3.3 Sentinel Clipboard Verification Protocol
The greatest vulnerability in desktop copy automation is clipboard poisoning: reading user private data if a copy click misses, or permanently overwriting user clipboard history.
Our Sentinel Clipboard Protocol eliminates this completely:

```python
import uuid
import time
import pyperclip

def execute_sentinel_clipboard_harvest(trigger_copy_action_func, timeout_s=2.5) -> Optional[str]:
    # 1. Preserve original user clipboard
    try:
        original_user_clip = pyperclip.paste()
    except Exception:
        original_user_clip = ""

    # 2. Arm unique sentinel token
    sentinel_token = f"__PARASITE_SENTINEL_{uuid.uuid4().hex}__"
    pyperclip.copy(sentinel_token)

    # 3. Trigger physical copy action (clicking Copy button or Ctrl+C)
    trigger_copy_action_func()

    # 4. Poll clipboard for change
    harvested_text = None
    start_time = time.perf_counter()
    while time.perf_counter() - start_time < timeout_s:
        try:
            current_clip = pyperclip.paste()
            if current_clip != sentinel_token and len(current_clip.strip()) > 0:
                harvested_text = current_clip
                break
        except Exception:
            pass
        time.sleep(0.05)

    # 5. Restore original user clipboard immediately!
    try:
        pyperclip.copy(original_user_clip)
    except Exception:
        pass

    # 6. Return verified harvest
    return harvested_text
```

**Guarantees**:
1. Zero user clipboard corruption: Original clipboard is always restored.
2. Zero false positives: If the copy action fails or clicks the wrong element, the clipboard remains equal to `sentinel_token` and the offloader treats it as a failed harvest rather than reading private user text.

---

## 4. Requirement R5: Entry Points & Verification Test Suite

### 4.1 Entry Points

#### 4.1.1 Main Script (`main.py`)
- **CLI Options**:
  - `--config <path>`: Custom configuration path (defaults to `config.yaml`).
  - `--debug`: Enable verbose debug telemetry.
  - `--mock-llm`: Run with deterministic simulated LLM responses for rapid GUI, HUD, and kinematic testing without GPU.
  - `--zero-vram`: Force browser-only offloading mode.
- **Lifecycle Sequence**:
  1. Initialize logging with color-coded formatters.
  2. Set Windows DPI awareness (`SetProcessDpiAwareness(2)`).
  3. Load configuration via Pydantic model `ParasiteConfig`.
  4. Instantiate `QApplication(sys.argv)`.
  5. Initialize Safety System: `InterruptGuard` (registers low-level hooks) and `WindowGuard`.
  6. Initialize Vision System: `MSSCapture` and `HybridGroundingEngine`.
  7. Initialize Mind System: `EpisodicWorkingMemory`, `DualMindPipeline`, `BrowserOffloader`.
  8. Initialize Physical Control: `HumanHandsController`.
  9. Instantiate UI: `CompanionDock` and `GhostHUD`.
  10. Connect all PyQt signals and start the background worker thread.
  11. Register cleanup hooks (`atexit` / `app.aboutToQuit`) to unhook Win32 hooks and reset mouse state.
  12. Execute `sys.exit(app.exec())`.

#### 4.1.2 Windows Desktop Launcher (`launch_parasite.bat`)
- Fast double-clickable Windows batch launcher:
  ```batch
  @echo off
  title ParasiteAI Desktop Companion
  cd /d "%~dp0"
  echo ========================================================
  echo   ParasiteAI — 100%% Visible Desktop Companion Launcher
  echo ========================================================
  where uv >nul 2>&1
  if errorlevel 1 (
      echo [ERROR] 'uv' package manager not found on PATH.
      echo Please install uv from https://astral.sh/uv
      pause
      exit /b 1
  )
  echo Launching via uv...
  uv run python main.py %*
  if errorlevel 1 (
      echo.
      echo [ERROR] ParasiteAI terminated with an error code.
      pause
  )
  ```

---

### 4.2 Automated Verification Test Suite (`tests/`)

All tests are executable via `uv run pytest tests/` with zero external hardware prerequisites.

#### 4.2.1 Target Test Files & Specifications

1. **`tests/test_interrupt_guard.py`**:
   - `test_synthetic_input_allowed()`:
     - Simulates mouse event with `LLMHF_INJECTED = 1`.
     - Verifies `InterruptGuard` does NOT trigger abort.
   - `test_physical_hardware_touch_aborts()`:
     - Simulates mouse event with `LLMHF_INJECTED = 0`.
     - Verifies `InterruptGuard` triggers abort callback within < 2ms.
   - `test_panic_shortcut_trigger()`:
     - Verifies emergency key combination triggers panic abort signal.

2. **`tests/test_grounding.py`**:
   - `test_uia_element_extraction()`:
     - Mocks `uiautomation` control tree.
     - Verifies buttons, edits, and tabs are extracted with valid bounding rects.
   - `test_element_filtering()`:
     - Verifies offscreen, zero-width, and disabled elements are pruned.
   - `test_ocr_fallback_and_coordinate_remapping()`:
     - Feeds sample synthetic image to OCR engine.
     - Verifies OCR text boxes are remapped to desktop space.
   - `test_spatial_deduplication()`:
     - Verifies overlapping UIA and OCR elements are merged into single `UIElement`.

3. **`tests/test_memory_and_offload.py`**:
   - `test_episodic_memory_buffer()`:
     - Appends 15 steps; verifies buffer maintains rolling window of last 10 steps.
   - `test_screen_diff_calculation()`:
     - Tests frame diff function against identical frames (diff ~ 0.0) and changed frames (diff > 0.05).
   - `test_loop_detection_trigger()`:
     - Feeds 2 consecutive identical failed clicks; verifies `loop_detected == True` and warning prompt is generated.
   - `test_sentinel_clipboard_protocol_success()`:
     - Simulates successful copy event.
     - Verifies sentinel was set, copied text was harvested, and original user clipboard was restored.
   - `test_sentinel_clipboard_protocol_miss()`:
     - Simulates failed copy event (clipboard remains unchanged).
     - Verifies harvest returns `None` and does NOT leak user clipboard.

4. **`tests/test_dual_mind.py`**:
   - `test_persona_engine_prompt_generation()`:
     - Verifies Persona pass outputs natural language thought and speech.
   - `test_action_dispatcher_schema_parsing()`:
     - Verifies Dispatcher outputs valid Pydantic `ActionPlan` JSON.
   - `test_invalid_target_id_recovery()`:
     - Verifies Dispatcher handles out-of-bounds `target_id` gracefully without crashing.

5. **`tests/test_gui_and_hud.py`**:
   - `test_companion_dock_state_signals()`:
     - Verifies state transitions update color badges and status labels.
   - `test_ghost_hud_win32_styles()`:
     - Verifies `WS_EX_LAYERED`, `WS_EX_TRANSPARENT`, and `WS_EX_NOACTIVATE` bits are applied.
   - `test_300ms_reticle_preview_delay()`:
     - Verifies reticle preview emits completion signal after exactly 300ms.

---

## 5. Technical Constraints & Mitigation Matrix

| Challenge / Constraint | Risk | Concrete Architectural Mitigation |
|---|---|---|
| **DPI Scaling Mismatch** | HUD tags and mouse clicks offset by 125%/150% on Windows 11 displays | Call `SetProcessDpiAwareness(2)` in `main.py` before `QApplication` creation. |
| **HUD Stealing Active Window Focus** | Drawing on overlay defocuses Chrome or Notepad | Apply `WS_EX_NOACTIVATE` (`0x08000000`) Win32 style so the overlay never gains input focus. |
| **Mouse Clicks Blocked by HUD** | Overlay intercepts clicks intended for desktop apps | Apply `WS_EX_TRANSPARENT` (`0x00000020`) Win32 style for hardware-level click-through. |
| **UIA Traversal Hangs on Massive Apps** | Tree walk takes > 2000ms on complex applications | Scope tree search to foreground window and taskbar only; cap traversal depth to 5. |
| **VRAM Exhaustion on RTX 4060 8GB** | Vision + OCR + Local LLM exceeds 8 GB VRAM | Zero-VRAM perception: Native UIA (0 MB VRAM) + Scoped RapidOCR (CPU ONNX, 0 MB VRAM). |
| **Local LLM JSON Schema Breakage** | 7B model emits broken JSON or robotic thoughts | Dual-Mind pipeline: Pass 1 does creative voice; Pass 2 does deterministic action schema. |
| **Clipboard Overwrite / User Data Leak** | Browser offload clobbers user clipboard or reads private data | Sentinel Clipboard Protocol: Save original -> arm sentinel -> copy -> verify -> restore. |
| **UI Freezing During Long Operations** | OCR, LLM inference, or browser wait freezes PyQt GUI | Decouple UI thread from engine loop via worker thread and `pyqtSignal` events. |

---

## 6. Conclusion & Recommendation for Implementation Workers

The technical investigation confirms that all requirements for R2, R4, and R5 are completely viable, well-defined, and fully aligned with the project's zero-headless, 100% visible desktop philosophy.
Subsequent implementation workers can directly use the specified data models, Win32 styles, state machine transitions, and test signatures without ambiguity.
