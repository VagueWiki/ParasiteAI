# Project: ParasiteAI

## Architecture
ParasiteAI is a 100% visible, desktop-native local AI assistant operating directly on the physical Windows desktop with zero headless browsers, zero invisible scrapers, and zero CLI-only interfaces.

The architecture comprises:
1. **Foundation & Config (`parasite_ai/config.py`, `config.yaml`, `pyproject.toml`)**:
   - Environment management via `uv` on Python 3.12.
   - Pydantic-validated YAML configuration.
   - Zero-Config Local Brain Manager with pluggable backends (GGUF via llama-cpp-python / llama-server, and zero-VRAM browser offload).
2. **Safety & Physical Input Layer (`parasite_ai/safety/`, `parasite_ai/hands/`)**:
   - Win32 low-level hardware hooks (`WH_MOUSE_LL`, `WH_KEYBOARD_LL`) filtering `LLMHF_INJECTED` and `LLKHF_INJECTED`.
   - Cross-thread atomic interrupt token halting synthetic actions in < 2ms on physical touch.
   - Global panic abort triggers (`Esc`, `Ctrl+Alt+P`, screen corner slam).
   - Sensitive Window Guard detecting password managers, terminals, and elevated UAC prompts, with fail-safe vision masking.
   - Kinematic mouse trajectory generator (Cubic Bézier, Flash & Hogan Min-Jerk velocity profile, micro-jitter, terminal overshoot).
   - Unicode physical typing engine with natural human inter-key cadence jitter and `Shift+Enter` multiline safety.
3. **Visible UI Layer (`parasite_ai/ui/`)**:
   - Companion Dock: Always-on-top frameless PyQt6 widget showing character avatar, mood/state pills, live speech/thought bubbles, perception thumbnail, user goal input, and pause/panic controls.
   - Ghost-Hand HUD: Transparent fullscreen click-through Win32 layered overlay (`WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOPMOST`) rendering numbered Set-of-Mark boxes [#1..#N] and 300ms pre-click reticle.
4. **Perception, Cognition & Offload Layer (`parasite_ai/vision/`, `parasite_ai/mind/`)**:
   - Hybrid Screen Grounding: Tier 1 Win32 UI Automation tree walk + Tier 2 Scoped RapidOCR (CPU ONNX) + Tier 3 spatial deduplication.
   - Episodic Working Memory: Ring buffer tracking action history, loop detection (triggering on 3+ repeated failures), and screen diff verification.
   - Dual-Mind Cognitive Pipeline: Pass 1 (Persona Engine character monologue) + Pass 2 (Action Dispatcher deterministic JSON command).
   - Visible Browser Offloader: Chrome automation using physical desktop interactions and Sentinel Clipboard Verification (save -> sentinel UUID -> physical copy -> verify -> restore).
5. **Entry Points & Verification (`main.py`, `launch_parasite.bat`, `tests/`)**:
   - DPI-aware application bootstrapper.
   - Full automated test suite executing under `uv run pytest`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Python 3.12 Environment & Dependencies | `pyproject.toml` with `uv` pinning, dependencies (`pyqt6`, `uiautomation`, `rapidocr-onnxruntime`, `pynput`, `pyautogui`, `pydantic`, `pyyaml`, `pytest`, `mss`) | M1 | R1, Survey 1 |
| 2 | Configuration Schema | `config.yaml` and `parasite_ai/config.py` with Pydantic validation for UI, safety, paths, and models | M1 | R1, Survey 1 |
| 3 | Local Brain Manager | Pluggable local model manager (GGUF loader/downloader, zero-VRAM browser offload coordinator) | M1 | R1, Survey 1 |
| 4 | Win32 Low-Level Hardware Hooks | `WH_MOUSE_LL` & `WH_KEYBOARD_LL` inspecting `LLMHF_INJECTED` and `LLKHF_INJECTED` flags | M2 | R3, Survey 2 |
| 5 | <2ms Hardware Touch Interrupt | Atomic cancellation token aborting active mouse/keyboard movement in <2ms on physical touch | M2 | R3, Survey 2 |
| 6 | Global Panic Abort | Emergency abort hotkey (`Ctrl+Alt+P` / `Esc` / screen corner slam) instantly freezing actions | M2 | R3, Survey 2 |
| 7 | Sensitive Window Guard | Privacy shield monitoring active foreground window, pausing actions on password managers and admin terminals | M2 | R3, Survey 2 |
| 8 | Human Kinematic Mouse Movement | Realistic trajectories using Cubic Bézier, Min-Jerk velocity profile, micro-jitter, and overshoot | M2 | R3, Survey 2 |
| 9 | Unicode Physical Typing | `KEYEVENTF_UNICODE` typing with cadence jitter, surrogate pairs, and `Shift+Enter` multiline protection | M2 | R3, Survey 2 |
| 10 | Visible Companion Dock | Always-on-top desktop companion dock displaying character speech, thoughts, state/mood, perception, and controls | M3 | R2, Survey 3 |
| 11 | Ghost-Hand HUD Overlay | Click-through transparent Win32 overlay (`WS_EX_TRANSPARENT`) displaying Set-of-Mark boxes and 300ms pre-click reticle | M3 | R2, Survey 3 |
| 12 | Hybrid Screen Grounding | Win32 UI Automation tree walking combined with scoped RapidOCR fallback and spatial deduplication | M4 | R4, Survey 3 |
| 13 | Episodic Working Memory | Ring-buffer action memory with screen diff verification and 3-strike failure loop detection | M4 | R4, Survey 3 |
| 14 | Dual-Mind Cognitive Pipeline | Pass 1 Persona monologue generation + Pass 2 deterministic Action Dispatcher | M4 | R4, Survey 3 |
| 15 | Visible Browser Brain Offloader | Chrome physical automation with Sentinel Clipboard Verification (save, test UUID, copy, restore) | M4 | R4, Survey 3 |
| 16 | Application Entry Points | `main.py` (DPI-aware bootstrapper) and `launch_parasite.bat` | M5 | R5, Survey 3 |
| 17 | Test Suite & 100% Pass | Full unit and integration test suite under `tests/` verifying all acceptance criteria via `uv run pytest` | M5 | R5, Survey 3 |
| 18 | Adversarial Coverage Hardening | White-box stress testing and edge-case hardening for physical input, grounding, and memory | M5 | Project Pattern Tier 5 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Foundation & Zero-Config Setup | Features 1, 2, 3 (`pyproject.toml`, `config.yaml`, `parasite_ai/config.py`, `parasite_ai/mind/brain_manager.py`) | none | DONE |
| M2 | Safety & Physical Input Layer | Features 4, 5, 6, 7, 8, 9 (`parasite_ai/safety/`, `parasite_ai/hands/`) | M1 | DONE |
| M3 | Desktop Companion Dock & Ghost HUD | Features 10, 11 (`parasite_ai/ui/companion_dock.py`, `parasite_ai/ui/ghost_hud.py`) | M1 | DONE |
| M4 | Perception, Memory & Browser Offload | Features 12, 13, 14, 15 (`parasite_ai/vision/grounding.py`, `parasite_ai/mind/memory.py`, `dual_mind.py`, `offloader.py`) | M1, M2 | DONE |
| M5 | Integration, Entry Points & E2E Acceptance | Features 16, 17, 18 (`main.py`, `launch_parasite.bat`, pass 100% E2E test suite + adversarial hardening) | M1, M2, M3, M4 | BLOCKED: Iteration 1 Gate Fail (teamwork_challenger_m5_2_gen2 REQUEST_CHANGES: runtime exception boundary, loop panic isolation, goal queue flush, in-flight pause token) |

## Interface Contracts

### 1. Safety & Input (`parasite_ai/safety/` & `parasite_ai/hands/`)
- `InterruptGuard`:
  - `start() -> None`: Starts low-level hook thread.
  - `stop() -> None`: Unhooks and terminates thread.
  - `is_interrupted() -> bool`: Returns whether physical touch has occurred since last reset.
  - `reset_interrupt() -> None`: Clears interrupt flag.
  - `get_cancellation_token() -> threading.Event`: Returns event set immediately (<2ms) on physical touch.
  - `simulate_event(event_type: str, flags: int, vk_code: int) -> None`: Software hook injection for automated testing.
- `WindowGuard`:
  - `is_safe_to_operate() -> bool`: Returns `False` if active foreground window is protected or inaccessible.
  - `get_active_window_info() -> WindowInfo`: Returns title, process_name, and rect of foreground window.
- `MouseDriver`:
  - `move_to(x: int, y: int, duration_ms: float = None, cancellation_token: threading.Event = None) -> bool`: Human curved move. Returns `False` if cancelled.
  - `click(x: int, y: int, button: str = "left", cancellation_token: threading.Event = None) -> bool`: Reticle preview + click.
- `KeyboardDriver`:
  - `type_text(text: str, cadence_jitter_ms: tuple = (25, 75), cancellation_token: threading.Event = None) -> bool`: Types via `KEYEVENTF_UNICODE`.

### 2. UI Subsystem (`parasite_ai/ui/`)
- `CompanionDock(QWidget)`:
  - `update_state(state: str, mood: str) -> None`: States: `WATCHING`, `THINKING`, `DRIVING`, `OFFLOADING`, `USER OVERRIDE`.
  - `update_speech(persona_monologue: str, thought: str = None) -> None`: Updates speech/thought bubbles.
  - `update_perception_preview(qimage: QImage) -> None`: Shows downscaled perception capture.
  - Signals: `goal_submitted(str)`, `pause_toggled(bool)`, `panic_triggered()`.
- `GhostHUD(QWidget)`:
  - `set_targets(targets: list[UIElement]) -> None`: Renders numbered bounding boxes [#1..#N].
  - `show_reticle(x: int, y: int, duration_ms: int = 300) -> None`: Renders animated targeting reticle before click.
  - `clear_targets() -> None`: Clears HUD overlay.

### 3. Perception, Memory & Offload (`parasite_ai/vision/` & `parasite_ai/mind/`)
- `ScreenGrounder`:
  - `ground(window_filter: int = None) -> list[UIElement]`: Returns indexed interactive elements (`id`, `bbox`, `label`, `control_type`, `center`).
- `EpisodicMemory`:
  - `record_step(action: ActionPlan, success: bool, screen_diff: float) -> None`: Appends to episodic ring-buffer.
  - `is_in_loop() -> bool`: Returns `True` if last 3 consecutive actions failed or produced no screen diff.
  - `get_recent_history(n: int = 5) -> list[StepRecord]`: History context for planner.
- `BrowserOffloader`:
  - `query_web_ai(prompt: str, browser_type: str = "chrome") -> str`: Visible physical browser interaction with sentinel clipboard verification.

## Code Layout
```
g:\__Docs\ParasiteAI\
├── pyproject.toml
├── config.yaml
├── main.py
├── launch_parasite.bat
├── parasite_ai/
│   ├── __init__.py
│   ├── config.py
│   ├── safety/
│   │   ├── __init__.py
│   │   ├── interrupt_guard.py
│   │   └── window_guard.py
│   ├── hands/
│   │   ├── __init__.py
│   │   ├── kinematics.py
│   │   ├── mouse.py
│   │   └── keyboard.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── companion_dock.py
│   │   └── ghost_hud.py
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── capture.py
│   │   └── grounding.py
│   └── mind/
│       ├── __init__.py
│       ├── brain_manager.py
│       ├── memory.py
│       ├── dual_mind.py
│       └── offloader.py
└── tests/
    ├── __init__.py
    ├── test_interrupt_guard.py
    ├── test_grounding.py
    ├── test_memory.py
    ├── test_sentinel_clipboard.py
    └── test_kinematics.py
```
