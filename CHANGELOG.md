# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **End-to-End Local VLM (`Qwen2.5-VL-3B-Instruct-GGUF` + `mmproj`) Wiring (`parasite_ai.vision.foveated`, `parasite_ai.vision.vlm_grounder`, `parasite_ai.mind.brain_manager`, `parasite_ai.mind.dual_mind`, `parasite_ai.config`, `config.yaml`)**:
  - **Multimodal `LlamaCppBackend` (`MTMDChatHandler` / `Qwen25VLChatHandler`)**: Updated `LlamaCppBackend` (`brain_manager.py`) to accept `mmproj_path`, auto-discover companion `mmproj-*.gguf` vision projectors on disk, initialize `MTMDChatHandler` (with fallback to `Qwen25VLChatHandler`), expose `supports_vision()`, and format `image_base64` payloads into multimodal `image_url` + `text` chat messages.
  - **Curated VLM + `mmproj` Dual-File Downloader**: Added `ggml-org/Qwen2.5-VL-3B-Instruct-GGUF` (`Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf` + `mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf`) to `CURATED_MODELS` and `config.yaml`, and updated `LocalBrainManager.start_download()` to automatically download and GGUF-verify both the main VLM weights and the companion `mmproj` vision projector.
  - **Set-of-Mark Foveated VLM Composite (`FoveatedVisionEngine.build_vlm_composite`)**: Added `encode_image_to_data_uri()` and `build_vlm_composite()` in `foveated.py` to overlay `[#ID]` badges onto the active-window foveal crop (or macro desktop overview) and encode it to a `640px` base64 JPEG data URI.
  - **Closed-Loop Pipeline Integration (`DualMindPipeline.step`)**: Wired `FoveatedVisionEngine` and `VLMGrounder` into `DualMindPipeline` (`dual_mind.py`) so both Pass 1 (`generate_thought`) and Pass 2 (`generate_action`) receive the live annotated visual frame (`image_base64`), and integrated `VLMGrounder` coordinate parsing (`<|box_start|>`, `<|coord_start|>`, `[ymin, xmin, ymax, xmax]`) and hybrid UIA element snapping in Step 4a.

### Fixed
- **Console/Custom-Rendered Window OCR Grounding, Already-Open Target Focus, & Gameplay Completion Guards (`parasite_ai.vision.grounding`, `parasite_ai.mind.resolver`, `parasite_ai.mind.dual_mind`, `parasite_ai.mind.plan`, `parasite_ai.main`, `config.yaml`)**:
  - **Fix 1 — Console/Custom-Window Scoped RapidOCR & Container Deduplication (`grounding.py`, `config.yaml`)**:
    - Enabled `ocr_scoped_only: true` in `config.yaml` so RapidOCR crops directly to the active window rectangle rather than scanning all 100 desktop shortcuts.
    - Excluded OS window chrome and scrollbar pseudo-buttons (`Page down`, `Line down`, `Minimize`, `Maximize`, `Close`, `System`, `Text Area`) from `active_uia_count` so console (`conhost.exe`) and custom-rendered game windows always trigger Scoped RapidOCR (`active_uia_count == 0 < 6`), and filtered scrollbar buttons out of the Set-of-Mark list.
    - Fixed `_deduplicate_and_merge()` so full-window container UIA elements (`Document "Text Area"`, `Pane`, `Window`, or `uia_area > 6 * ocr_area`) no longer swallow contained OCR text lines during `compute_containment` deduplication.
    - Promoted open target windows matching `goal_keywords` to the active window root when OS foreground is `Program Manager` or `ParasiteAI Launcher`.
  - **Fix 2 — Already-Open Window Focus, Console Keyboard Interaction, & Conversational Suffix Stripping (`resolver.py`, `dual_mind.py`)**:
    - Stripped trailing conversational clauses (`"on your own"`, `"without my input"`, `"by yourself"`, etc.) in `UniversalAppResolver.extract_target_app()` and stripped Windows Taskbar running-window suffixes (`"- 1 running window"`) in `PrecisionAppMatcher.score_match()`.
    - Added Tier 0 already-open window detection in `UniversalAppResolver.resolve_launch_action()` and Section 3c/3d in `DualMindPipeline.step()` so when the target application window is already open on screen, the agent focuses it instead of re-double-clicking the desktop shortcut or toggling its taskbar button.
    - Added console (`conhost.exe`) interaction handling that focuses the console window via `SetForegroundWindow`, converts mouse clicks on OCR text/menus into keyboard input (`TYPE` option number + `Enter`, or `HOTKEY ["enter"]`) to avoid Windows QuickEdit selection pauses, and exempts console hosts from Win32 `GUITHREADINFO` caret verification.
  - **Fix 3 — Open-Ended Gameplay Step Completion Guard & Automatic Timestamped Log Archiving (`plan.py`, `dual_mind.py`, `main.py`)**:
    - Updated `verify_step_completion()` (`plan.py`) and Section 2 (`dual_mind.py`) so open-ended gameplay/autonomous interaction goals (`"play ..."`, `"on your own"`, `"without my input"`) require at least 3 in-app interaction steps before marking `StepIntent.NAVIGATE` as `COMPLETED` or accepting `ActionType.DONE`.
    - Updated `setup_logging()` (`main.py`) to automatically archive any existing non-empty `logs/parasite_debug.log` to a timestamped file (`logs/parasite_debug<HHMMam/pm>.log`) on startup, and archived the Warsim test run to `logs/parasite_debug0221pm.log`.
- **Pydantic Null-Field Coercion, CompanionDock Full Collapse Evasion, & Taskbar/Window Hijack Guards (`parasite_ai.mind.memory`, `parasite_ai.mind.brain_manager`, `parasite_ai.ui.companion_dock`, `parasite_ai.ui.bridge`, `parasite_ai.mind.dual_mind`)**:
  - **`ActionPlan` Null Field Coercion**: Added `@model_validator(mode="before")` on `ActionPlan` (`memory.py`) and null-field sanitization in `LocalBrainManager.generate_action()` (`brain_manager.py`) so explicit `null`/`None` values emitted by the 1.5B local model (e.g., `"submit": null` during `DOUBLE_CLICK`) coerce cleanly to their defaults (`submit=False`, `clear_first=True`, `wait_ms=500`, `scroll_amount=0`, `clicks=1`) instead of raising a `ValidationError`.
  - **`CompanionDock` "Half-Minimized" Layout & Self-Occlusion Fix**: Wrapped all widgets and sub-layouts below `header_frame` into a single collapsible `body_container` widget, set `main_card.setFixedHeight(48)` and activated layouts synchronously inside `minimize_dock()` so pending Qt `LayoutRequest` events from multi-line speech updates cannot re-expand the window to `578px` while minimized. Added `setWindowTitle("ParasiteAI CompanionDock")`, `UIBridge.evade_dock(x, y)`, and direct Win32 `SetWindowPos` relocation in `_evade_companion_dock_if_needed()` so the dock immediately shrinks to `56px` and vacates the target desktop icon area.
  - **Taskbar `DOUBLE_CLICK` Normalization & `NEED_SOON_MINIMIZE` Window Hijack Guard**: Added automatic downgrade of `DOUBLE_CLICK` to single `CLICK` on Windows Taskbar buttons (`window="Taskbar"` or `"running window"` in label) so taskbar clicks activate windows rather than toggling them back to minimized, and broadened Section 3 (`Non-target window hijack & lifecycle evaluation guard`) to intercept misdirected clicks (such as clicking `"Maximize"` on `notepad++.exe`) across all `NEED_SOON_MINIMIZE` non-target windows.
  - **Log Cycling**: Cycled `logs/parasite_debug.log` to `logs/parasite_debug0122pm.log`.

### Added
- **Left-Monitor Vision & Actuation Lock & Continuous Iteration CLI Harness (`parasite_ai.config`, `parasite_ai.vision.capture`, `parasite_ai.vision.grounding`, `parasite_ai.mind.dual_mind`, `parasite_ai.runtime`, `parasite_ai.main`)**:
  - **Left-Monitor Scoping (`monitor_index: 1`)**: Added `VisionConfig.monitor_index` (default `1` — Left/Primary Monitor `0 <= x < 1920, 0 <= y < 1080`) and `get_monitor_bounds(monitor_idx)` in `capture.py`.
  - **UIA & OCR Monitor Bounding Filter**: Updated `ScreenGrounder` (`grounding.py`) to filter out top-level windows, UIA child controls, and OCR boxes whose centers fall outside the target monitor (`x >= 1920`), and tracked `_last_active_win_rect` so `DualMindPipeline._get_effective_active_window()` resolves the topmost window on the Left Monitor even when OS keyboard focus rests on the Right Monitor (e.g., Antigravity IDE or Discord).
  - **Actuation Coordinate Guard**: Updated `ActionDispatcher.validate_coordinates()` (`dual_mind.py`) to reject any mouse click/move coordinates outside the configured monitor bounds (`0 <= x < 1920, 0 <= y < 1080`).
  - **Continuous Automatic Iteration CLI Flags**: Added `--monitor-index`, `--auto-exit-on-complete`, and `--max-steps` CLI flags (`main.py`, `runtime.py`) so Antigravity can launch bounded single-episode test runs, inspect `logs/parasite_debug.log` on exit, patch bugs, and re-run autonomously.
- **Intermediate Platform Launcher & Steam Launch Options Handling (`parasite_ai.mind.dual_mind`, `parasite_ai.mind.plan`, `parasite_ai.vision.grounding`, `parasite_ai.mind.brain_manager`, `parasite_ai.config`)**:
  - **Foreground-Scoped OCR Trigger**: Updated `ScreenGrounder.extract_elements()` to evaluate `active_uia_count` (UIA controls in the active foreground window) rather than total desktop UIA count so custom-rendered windows (such as Steam's `steamwebhelper.exe` Launch Options dialog or OpenGL/DirectX game menus) automatically trigger scoped RapidOCR even when 100+ background desktop icons exist.
  - **Intermediate Launcher Detection (`is_intermediate_launcher_window`)**: Added detection for game platform launchers and launch-options modals (`steam.exe`, `steamwebhelper.exe`, `epicgameslauncher.exe`, `riotclientservices.exe`, `"Launch Options"`) so `DualMindPipeline.step()` and `verify_step_completion()` do not prematurely declare victory (`DONE`) when a game's Launch Options dialog appears, instead clicking `"Play"` / `"Launch"` or pressing `Enter` until the actual game window launches.
  - **Hotkey `#ID` & Single-Letter Desktop Hotkey Sanitization**: Removed `"or hotkey"` from the Pass 1 `DECISION` prompt, added automatic conversion of `HOTKEY ["#<id>"]` to `CLICK` on `target_id=<id>`, redirected bare single-character desktop hotkeys (like `HOTKEY ["r"]`) to `resolve_launch_action()`, and extended the oscillation detector to catch repeated `HOTKEY` and `MINIMIZE_WINDOW` loops.
  - **Desktop Shortcut Minimize Guard & Context Menu Dismissal**: Prevented `MINIMIZE_WINDOW` from calling `ShowWindow(SW_MINIMIZE)` on the Windows Desktop (`Progman`/`WorkerW`) or targeting the target app's desktop shortcut, and added automatic `Esc` dismissal of stray desktop right-click `"Context"` menus before double-clicking desktop icons.
  - **Contingency Step Return to Paused Step (`LivingPlan.advance_step`)**: Fixed `check_and_insert_contingencies()` and `LivingPlan.advance_step()` so completing a stagnation contingency step returns execution to the paused `Step 1 (LAUNCH_OR_ACTIVATE)` rather than skipping ahead to `CONCLUDE`.
  - **Log Cycling**: Cycled `logs/parasite_debug.log` to `logs/parasite_debug1224pm.log`.
- **Dynamic Perception & Reasoning Upgrades (Stage 1) (`parasite_ai.vision.grounding`, `parasite_ai.mind.resolver`, `parasite_ai.mind.brain_manager`, `parasite_ai.mind.dual_mind`, `parasite_ai.mind.plan`, `parasite_ai.main`)**:
  - **Spaceless & Compound Fuzzy Grounding**: Added normalized spaceless/compound token matching (`re.sub(r"[^a-z0-9\+#]", "", ...)`) in `ScreenGrounder` and `PrecisionAppMatcher.score_match()` so compound queries like `"riftwizard"` match desktop icons like `"Rift Wizard 2"` (`score=0.88`, `is_goal_match=True`).
  - **Pass 1 Background/Desktop Target Visibility & Structured Self-Critique**: Enriched `ScreenGrounder.format_concise_scene_summary()` to surface top background/desktop `[#ID]` targets to Pass 1, and updated Pass 1 (`generate_thought` and `PersonaConfig.system_prompt`) to emit structured `<thought>` blocks (`OBSERVATION`, `CRITIQUE`, `DECISION` with `[#ID]`) before 1-sentence character speech.
  - **Semantic `MINIMIZE_WINDOW` / `CLOSE_WINDOW` Target Validation**: Updated `ActionDispatcher.dispatch()` so if the LLM passes a non-button or wrong element `target_id` (such as `Document "Text Area"`) for `MINIMIZE_WINDOW` or `CLOSE_WINDOW`, it automatically resolves the actual `"Minimize"` or `"Close"` `Button` belonging to that window instead of clicking inside the window body.
  - **Child-Element Error Dialog Detection (`is_error_dialog_window`)**: Added inspection of grounded child `Text`/`Dialog` elements (e.g. `"Windows cannot find 'riftwizard'..."`) in addition to window titles, preventing `DualMindPipeline.step()` and `verify_step_completion()` from mistaking an `explorer.exe` launch error modal for the target application.
  - **Removed Brittle Thought Regex Overrides**: Removed `extract_target_app(persona_out.thought)` fallback and hardened `UniversalAppResolver.extract_target_app()` to ignore window-closing/minimizing goals (`"close ..."`, `"minimize ..."`) and conversational prepositions (`"start with ..."`).
  - **Log Noise Suppression & Cycling**: Suppressed `comtypes` DEBUG log flooding in `setup_logging()` and cycled `logs/parasite_debug.log` to `logs/parasite_debug1207pm.log`.
- **Companion Dock Window Controls (`parasite_ai.ui.companion_dock`, `parasite_ai.ui.bridge`, `parasite_ai.main`)**:
  - Added **Minimize (`—` / `□`)** and **Close (`✕`)** buttons to `CompanionDock`'s top-right header bar (`BtnMinimize` and `BtnClose`).
  - Added `minimize_dock()`, `restore_dock()`, `toggle_minimize_dock()`, `close_dock()`, and `evade_coordinates()` slots on `CompanionDock`, plus `minimize_dock()` and `restore_dock()` signals on `UIBridge`.
  - Connected `sig_close_requested` to `ParasiteApp._on_dock_close_requested` for clean application shutdown when the Close button is clicked.
- **Self-Occlusion Auto-Evasion (`parasite_ai.mind.dual_mind`, `parasite_ai.ui.companion_dock`)**:
  - Added `ActionDispatcher._evade_companion_dock_if_needed()` and `get_companion_dock_rect()` to detect when a click/double-click target (such as a desktop icon like `"Rift Wizard 2"` at `(1732, 528)`) overlaps `CompanionDock`'s own geometry, automatically collapsing and shifting the dock out of the way before clicking.
- **Window Lifecycle Evaluation — Minimize ("Need Soon") vs. Close ("Don't Need Anytime Soon") (`parasite_ai.mind.dual_mind`, `parasite_ai.mind.memory`, `parasite_ai.mind.brain_manager`)**:
  - Added `ActionType.MINIMIZE_WINDOW` and `ActionType.CLOSE_WINDOW` to `ActionType` and `ActionDispatcher.dispatch()`.
  - Added deterministic `evaluate_window_disposition(window_title, process_name, user_goal, target_app)` classifying open windows into `"TARGET"`, `"NEED_SOON_MINIMIZE"` (persistent workspaces, IDEs, browsers, Steam, Discord, ParasiteAI Launcher), and `"DONT_NEED_CLOSE"` (modal error dialogs, stray File Explorer folder views, finished temporary utilities like Notepad/Calculator).
  - Updated `DualMindPipeline.step()` to automatically close `"DONT_NEED_CLOSE"` windows and minimize `"NEED_SOON_MINIMIZE"` windows when they obstruct desktop targets or intercept focus.

### Fixed
- **Browser Offloader Demo Chip Click & Screen-Center Clicking Loop (`parasite_ai.mind.offloader`)**:
  - Hardened `BrowserOffloader._find_prompt_target()` to strictly disqualify `Button`, `Hyperlink`, `ListItem`, `MenuItem`, and long sentence elements so Gemini starter/demo question chips are never clicked as the prompt input box.
  - Updated fallback prompt coordinate to `rect[3] - 68` (bottom input bar, below center-screen suggestion chips) and added `force_ocr=True` retry when Chrome exposes fewer than 3 UIA elements.
  - Added window title check (`get_window_title`) to skip redundant `Ctrl+L` URL re-navigation when Chrome is already on the target web AI tab.
  - Removed the blind `mouse_driver.click(prompt_x, prompt_y - 200)` fallback inside `trigger_copy()` that repeatedly clicked the center of the screen every 0.5s while polling for a response.

### Added
- Unified High-Fidelity Debug Logging Subsystem (`parasite_ai.main`, `parasite_ai.config`): Rotating file logger at `logs/parasite_debug.log` (15 MB rotation, 5 backups, millisecond timestamps, thread names, module and line numbers). Added `--debug` and `--log-file` CLI arguments.
- Diagnostic Tracing across Cognition, Execution & Misfires (`parasite_ai.mind.brain_manager`, `parasite_ai.mind.dual_mind`, `parasite_ai.mind.affordance`): Direct logging of Pass 1 persona prompts and monologues, Pass 2 action prompts, raw model responses, parsed JSON actions, localized ROI diff verification results, strike transitions, caret check suppression, and sandboxed CLI execution tokens, exit codes, and stdout/stderr streams.
- Localized ROI Diffing (`parasite_ai.mind.dual_mind`): `BoundingBox.pad(padding_px=20)` with multi-monitor virtual screen bounds clamping (`3840x1080 @ 100% DPI`), scoping post-action visual difference verification to padded action targets (`extract_action_target_roi()`).
- Win32 Caret Focus Verification (`parasite_ai.mind.dual_mind`): 64-bit Win32 `GUITHREADINFO` ctypes struct and `check_caret_focus` verifying `(flags & GUI_CARETBLINKING) or (hwndCaret != 0)` prior to emitting `ActionType.TYPE` with a 250ms polling loop.
- Start Search Cadence Buffer (`parasite_ai.mind.resolver`): 250ms cadence pause in `UniversalAppResolver` post-`Win` key chord with millisecond preemption checks.
- Dynamic Living Plan schemas (`StepIntent`, `StepStatus`, `PlanStep`, `LivingPlan`) in `parasite_ai.mind.plan`.
- Strategic Gemini consultation protocol (`format_gemini_consultation_prompt`, `extract_strategic_blueprint_json`, `parse_gemini_consultation_response`) for multi-step reasoning.
- Non-blocking hard termination mechanism on `Ctrl+Alt+K` via `taskkill /F /T /PID` and `os._exit(1)`.
- Export alias `WebOffloadBackend = BrowserOffloadBackend` in `parasite_ai.mind.brain_manager`.
- Foveated Multi-Scale Perception Engine (`parasite_ai.vision.foveated`): 1:1 unscaled native pixel crops around cursor/active window targets alongside a lightweight global macro overview, with 64-bit `dHash` visual change gating and adaptive rate limiting.
- Universal Application Resolver (`parasite_ai.mind.resolver`): Generic multi-tier target resolution across arbitrary Windows applications (Tier 1 Set-of-Mark matching, Tier 2 Start Search chord, Tier 3 Run dialog fallback) without hardcoded application lists.
- Multimodal Visual Grounder (`parasite_ai.vision.vlm_grounder`): Local Qwen2.5-VL tag/box parsing with hybrid coordinate snapping to nearby UIA/SOM controls.
- Dynamic Living Plan integration into `DualMindPipeline`: automated stage sequencing, progress tracking, and unexpected modal dialog contingency insertion.

### Fixed
- Fixed crowded desktop UIA truncation and occlusion dropping target application shortcuts (`parasite_ai.vision.grounding`):
  - Raised desktop sibling capacity to 250 elements for explorer windows (`Program Manager`, `WorkerW`, `Desktop`).
  - Added in-flight keyword preservation during accessibility tree walks so items matching user goal keywords are never dropped by per-window limits or `is_occluded` bounding box checks.
  - Deduplicated child `TextControl` and `ImageControl` sub-nodes under desktop `ListItemControl` nodes to eliminate element slot bloat.
- Fixed Run dialog (`Win+R`) multi-word failure and modal error dialog loop (`parasite_ai.mind.dual_mind`, `parasite_ai.mind.resolver`):
  - Added auto-dismissal for Windows modal error dialogs (`Windows cannot find '...'`) via Enter/Esc to prevent UI deadlock.
  - Automatically dismisses Run dialog and falls back to Windows Start Search when target application names contain spaces (e.g. `"rift wizard"`).
  - Upgraded desktop shortcut launching to `DOUBLE_CLICK`, and added active window obscuration detection with `Win+D` desktop reveal.
  - Fixed File Explorer folder search box hijack: restricted Start Search detection to system search hosts (`SearchApp.exe`, `SearchHost.exe`, `StartMenuExperienceHost.exe`, and taskbar explorer windows).
  - Added support for `"play"`, `"play some"`, and `"play the game"` in `UniversalAppResolver.extract_target_app` with a generic word blacklist (`"games"`, `"app"`, etc.).
- Default brain configuration in `config.yaml` set to `local_llm`.
- Application launcher `launch_parasite.bat` now explicitly passes `--brain-mode local_llm %*`.
- Eliminated legacy hardcoded application dictionary `app_map` in `DualMindPipeline.step`.
- Virtual desktop metrics in `parasite_ai.vision.capture`: dynamic `get_virtual_screen_bounds()` replaces fixed `(1080, 1920)` synthetic fallback for dual-monitor configurations.
- Browser offload prompt delivery in `parasite_ai.mind.offloader`: replaced character-by-character `KEYEVENTF_UNICODE` typing with high-speed `<100ms` `Ctrl+V` clipboard paste and safe user clipboard restoration.
- Local brain manager execution decoupling: `LocalBrainManager._init_backend` retains `BrainMode.LOCAL_LLM` and sets `BrainState.NO_MODEL_PRESENT` when local models are missing, without silently mutating mode to browser offload.
- `LocalBrainManager.generate`: raises `RuntimeError` when local model is unavailable in local mode rather than silently dispatching web offload.
- `LocalBrainManager.generate_thought`: returns graceful character monologue fallback without web offload if local inference fails.
- Screen corner slam panic handling in `PanicManager`: added 1.0-second edge-triggered debouncing to eliminate Qt event loop flooding.
- Sentinel harvest protocol in `SentinelClipboardVerifier.execute_harvest`: added periodic retriggering of `trigger_copy_action` during polling loop to prevent timeout errors.

### Fixed
- Document Content Typing and Stream-of-Consciousness Isolation (`parasite_ai.mind.dual_mind`): Isolated avatar persona monologue speech/thought from physical document typing. Persona thoughts are strictly forbidden from being injected into `action_plan.text`. Added support for goal intent keywords (`intro`, `introduction`, `introduce`) to type canonical companion introduction (`"Hello! I am Parasite, an autonomous desktop companion."`) and suppress premature enter keys (`submit=False`).
- Menu Bar & Interactive Control Typing Protection (`parasite_ai.mind.dual_mind`): Prevented `CLICK_AND_TYPE` from typing document content into non-text controls (`MenuItem`, `Button`, `TabItem`, `ScrollBar`). If an editor canvas (`Document`/`Edit`) is not in the grounded elements list, redirected target to the active window's client center to safely focus the document canvas instead of triggering menu accelerators or File/Save dialogs.
- Pass 2 Active Step Awareness (`parasite_ai.mind.dual_mind`): Prefixed `persona_intent` with active plan step description (`Active Step: ...`) so local LLM does not repeat application launch actions when target application is already active.
- Human Interrupt Recovery Latency (`parasite_ai.config`, `parasite_ai.safety.interrupt_guard`): Reduced `override_pause_duration_sec` from 10.0s down to 2.5s for fast control yield and recovery.
- Browser Offloader Full-Viewport Container Filtering (`parasite_ai.mind.offloader`): Filtered out full-page document wrappers from prompt target localization, preventing dead-center clicks into blank web page space.
- Companion Dock Internal Monologue Autoscroll (`parasite_ai.ui.companion_dock`): Fixed cursor positioning bug where `appendPlainText` left cursor at position 0, causing `ensureCursorVisible()` to force the viewport to the top of the text box. Cursor now advances to end and explicitly scrolls vertical scrollbar to maximum, ensuring the newest thought line is always visible.
- Unintended Gemini web offload on cognitive Pass 1 during local LLM execution.
- `OffloadHarvestError` timeouts caused by one-shot copy button clicking and clipboard verification deadlocks during browser offload.
- Companion Dock UI freezes during rapid screen corner mouse movements.

## [0.1.0] - 2026-10-29

### Added
- Python 3.12 environment with `uv` dependency management and lockfile pinning.
- Pydantic V2 configuration architecture (`AppConfig`, `SystemConfig`, `BrainConfig`, `UIConfig`, `SafetyConfig`, `HandsConfig`, `VisionConfig`).
- Pluggable `LocalBrainManager` supporting GGUF validation, streaming non-blocking downloads, CUDA 12 GPU acceleration via `llama-cpp-python`, and Zero-VRAM browser offload.
- Low-level Win32 hardware hooks (`WH_MOUSE_LL`, `WH_KEYBOARD_LL`) with injected input filtering (`LLMHF_INJECTED`, `LLKHF_INJECTED`).
- Sub-2ms hardware touch interrupt guard preemption token.
- Global emergency panic management (`Esc`, `Ctrl+Alt+P`, `Ctrl+Alt+Backspace`, screen corner slam).
- Privacy protection with `WindowGuard` monitoring password managers, terminals, and elevated UAC windows.
- Natural human kinematic mouse trajectories (Cubic Bézier, Flash & Hogan Min-Jerk velocity profile, micro-jitter, terminal overshoot).
- Unicode physical keyboard driver with human cadence jitter and `Shift+Enter` multiline safety.
- Always-on-top visible PyQt6 `CompanionDock` with character avatar, mood/state pills, speech/thought bubbles, and pause/panic controls.
- Transparent fullscreen click-through `GhostHUD` (`WS_EX_LAYERED | WS_EX_TRANSPARENT`) rendering Set-of-Mark numbered boxes and 300ms pre-click reticle.
- Hybrid screen grounding combining Win32 UI Automation tree walking with scoped RapidOCR fallback.
- Episodic working memory ring buffer with visual dHash screen difference checking and 3-strike failure loop detection.
- Dual-mind cognitive pipeline: Pass 1 character monologue (Persona Engine) and Pass 2 deterministic JSON action generation (Action Dispatcher).
- Physical Chrome offloader using visible browser automation and Sentinel Clipboard Verification.
- Master `RuntimeOrchestrator` coordinating GUI, background cognitive worker, and Win32 hook threads.
- Desktop entry points `main.py`, `launch_parasite.bat`, and emergency process killer `kill_parasite.bat`.
